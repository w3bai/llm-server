from fastapi import FastAPI, HTTPException, Depends, WebSocket, BackgroundTasks, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.models import (
    CompetitionCreate,
    CompetitionResponse,
    CompetitionTaskResponse,
    CompetitionStatusResponse,
    Query,
    FrontendQuery,
)
from app.data_ingestion.github_loader import GitHubLoader
from app.data_ingestion.web_scraper import WebScraper
from app.data_processing.text_processor import TextProcessor
from app.data_processing.reranker import Reranker
from app.database.vector_store import VectorStore
from app.llm.interface import LLMInterface
from app.database.supabase_utils import supabase_manager
from app.utils.prompt_helpers import (
    build_system_prompt,
    build_human_prompt,
    build_context,
)
from middleware import verify_api_key
import logging
import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
app.add_middleware(SlowAPIMiddleware)

github_loader = GitHubLoader()
text_processor = TextProcessor()
vector_store = VectorStore()
llm_interface = LLMInterface()
reranker = Reranker()

# Store for active WebSocket connections
active_connections = {}


@app.get("/")
async def root():
    return {"message": "Server is up and running!"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post(
    "/competitions",
    response_model=CompetitionTaskResponse,
    dependencies=[Depends(verify_api_key)],
)
def scrape_competition(
    competition: CompetitionCreate, background_tasks: BackgroundTasks
):
    try:
        # Create a new competition with 'pending' status
        new_competition = supabase_manager.create_competition(
            name=competition.name,
            github_url=str(competition.github_url),
            docs_url=str(competition.docs_url) if competition.docs_url else None,
            status="pending",
        )

        # Start the scraping task in the background
        background_tasks.add_task(
            scrape_competition_task, new_competition["id"], competition
        )

        return CompetitionTaskResponse(
            competition_id=new_competition["id"], status="pending"
        )

    except Exception as e:
        logging.error(f"Error initiating competition creation: {str(e)}")
        supabase_manager.update_competition, competition_id, {"status": "failed"}
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate competition creation: {str(e)}"
        )


async def scrape_competition_task(competition_id: str, competition: CompetitionCreate):
    try:
        # Load and process GitHub data
        github_files = await run_in_threadpool(
            github_loader.get_repo_contents, competition.github_url
        )
        for file in github_files:
            content = await run_in_threadpool(github_loader.get_file_content, file)
            is_code = file.name.endswith((".sol", ".rs", ".go"))
            chunks = await run_in_threadpool(
                text_processor.chunk_text, content, is_code=is_code
            )
            for i, chunk in enumerate(chunks):
                try:
                    tokens = await run_in_threadpool(
                        text_processor.estimate_tokens, chunk
                    )
                    embedding = await run_in_threadpool(
                        text_processor.generate_embedding, chunk
                    )
                    logging.info(f"Processing chunk {i} with {tokens} tokens")
                    await run_in_threadpool(
                        vector_store.upsert,
                        [
                            (
                                f"{competition_id}_github_{file.path}_{i}",
                                embedding,
                                {
                                    "text": chunk,
                                    "source": "github",
                                    "path": file.path,
                                    "competition_id": competition_id,
                                },
                            )
                        ],
                    )
                except ValueError as e:
                    logging.warning(f"Skipping chunk due to: {str(e)}")

        # Load and process documentation
        if competition.docs_url:
            web_scraper = WebScraper(competition.docs_url, max_pages=300)
            crawl_status = await web_scraper.scrape_site()

            # Process pages as they are crawled
            while crawl_status["status"] != "completed":
                for page in crawl_status["data"]:
                    await process_page(page, competition_id)

                # If there are more pages to fetch
                if crawl_status.get("next"):
                    crawl_status = await web_scraper.get_scraped_data(
                        crawl_status["next"]
                    )
                else:
                    await asyncio.sleep(30)  # Wait before checking again
                    crawl_status = await web_scraper.get_scraped_data(
                        crawl_status["id"]
                    )

            # Process any remaining pages in the final batch
            for page in crawl_status["data"]:
                await process_page(page, competition_id)

        # Update competition status to 'completed'
        await run_in_threadpool(
            supabase_manager.update_competition, competition_id, {"status": "completed"}
        )

    except Exception as e:
        logging.error(f"Error creating competition: {str(e)}")
        # Update competition status to 'failed'
        await run_in_threadpool(
            supabase_manager.update_competition, competition_id, {"status": "failed"}
        )
        # Delete associated data from vector store
        await run_in_threadpool(vector_store.delete_by_competition_id, competition_id)


async def process_page(page, competition_id):
    content = page["markdown"]  # Use markdown content
    chunks = await run_in_threadpool(text_processor.chunk_text, content, is_code=False)
    for i, chunk in enumerate(chunks):
        try:
            tokens = await run_in_threadpool(text_processor.estimate_tokens, chunk)
            embedding = await run_in_threadpool(
                text_processor.generate_embedding, chunk
            )
            logging.info(f"Processing chunk {i} with {tokens} tokens")
            await run_in_threadpool(
                vector_store.upsert,
                [
                    (
                        f"{competition_id}_doc_{page['metadata']['sourceURL']}_{i}",
                        embedding,
                        {
                            "text": chunk,
                            "source": "documentation",
                            "url": page["metadata"]["sourceURL"],
                            "title": page["metadata"]["title"],
                            "competition_id": competition_id,
                        },
                    )
                ],
            )
        except ValueError as e:
            logging.warning(f"Skipping chunk due to: {str(e)}")


@app.get("/competitions", dependencies=[Depends(verify_api_key)])
async def list_competitions():
    return supabase_manager.list_competitions()


@app.get(
    "/competitions/{competition_id}",
    response_model=CompetitionResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_competition(competition_id: str):
    competition = supabase_manager.get_competition(competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    return CompetitionResponse(**competition)


@app.get(
    "/competitions/{competition_id}/status",
    response_model=CompetitionStatusResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_competition_status(competition_id: str):
    competition_status = supabase_manager.get_competition_status(competition_id)
    if not competition_status:
        raise HTTPException(status_code=404, detail="Competition not found")

    vector_count = vector_store.count_vectors(competition_id)

    return CompetitionStatusResponse(
        id=competition_status["id"],
        name=competition_status["name"],
        status=competition_status["status"],
        created_at=competition_status["created_at"],
        vector_count=vector_count,
    )


@app.delete(
    "/competitions/{competition_id}",
    response_model=dict,
    dependencies=[Depends(verify_api_key)],
)
async def delete_competition(competition_id: str):
    deleted = supabase_manager.delete_competition(competition_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Competition not found")

    # Delete associated data from vector store
    vector_store.delete_by_competition_id(competition_id)

    return {"message": f"Competition {competition_id} has been deleted"}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    logger.info(f"WebSocket connection attempt from client: {client_id}")
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for client: {client_id}")
        active_connections[client_id] = websocket
        try:
            while True:
                data = await websocket.receive_text()
                logger.info(f"Received message from client {client_id}: {data}")
                # Echo the message back to the client
                await websocket.send_text(f"Server received: {data}")
        except Exception as e:
            logger.info(f"WebSocket disconnected for client: {client_id}")
        finally:
            if client_id in active_connections:
                del active_connections[client_id]
    except Exception as e:
        logger.error(f"Error in WebSocket connection for client {client_id}: {str(e)}")
    finally:
        logger.info(f"WebSocket connection closed for client: {client_id}")


@app.post("/query", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def query(request: Request, query: Query, background_tasks: BackgroundTasks):
    competition = supabase_manager.get_competition(query.competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    # Create a record in the queries table
    query_record = supabase_manager.create_query(
        competition_id=query.competition_id, question=query.question, source="discord"
    )

    # Start the LLM query process in the background
    background_tasks.add_task(process_llm_query, competition, query)

    return {"message": "Query processing started", "status": "pending"}


async def process_llm_query(competition, query):
    try:
        question_embedding = text_processor.generate_embedding(query.question)
        results = vector_store.query(question_embedding, competition["id"], top_k=50)

        if not results or not hasattr(results, "matches") or len(results.matches) == 0:
            logging.warning("No results found in vector store")
            await send_websocket_message(
                query.client_id, {"error": "No results found in vector store"}
            )
            return

        passages = [
            match.metadata["text"]
            for match in results.matches
            if "text" in match.metadata
        ]

        reranked_passages = reranker.rerank(query.question, passages, top_k=20)

        context = build_context(reranked_passages)

        system_prompt = build_system_prompt()
        human_prompt = build_human_prompt(competition["name"], context, query.question)

        response = llm_interface.generate_response(system_prompt, human_prompt)

        # Send the response back through the WebSocket
        await send_websocket_message(
            query.client_id, {"response": response, "query_id": query.query_id}
        )

    except Exception as e:
        logging.error(f"Error processing LLM query: {str(e)}")
        await send_websocket_message(
            query.client_id, {"error": str(e), "query_id": query.query_id}
        )
        supabase_manager.update_query(query_id, {"is_success": False})


async def send_websocket_message(client_id, message):
    logger.info(f"client_id: {client_id}")
    if client_id in active_connections:
        logger.info(
            f"client id: {client_id} is in active_connections: {active_connections}"
        )
        logger.info(f"message: {message}")
        await active_connections[client_id].send_text(json.dumps(message))


@app.post("/frontend/query", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def frontend_query(request: Request, query: FrontendQuery):
    competition = supabase_manager.get_competition(query.competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    # Create a record in the queries table
    query_record = supabase_manager.create_query(
        competition_id=query.competition_id, question=query.question, source="frontend"
    )

    return StreamingResponse(
        process_frontend_query(competition, query), media_type="text/event-stream"
    )


def process_frontend_query(competition, query):
    try:
        question_embedding = text_processor.generate_embedding(query.question)
        results = vector_store.query(question_embedding, competition["id"], top_k=50)

        if not results or not hasattr(results, "matches") or len(results.matches) == 0:
            yield "data: No results found in vector store\n\n"
            return

        passages = [
            match.metadata["text"]
            for match in results.matches
            if "text" in match.metadata
        ]

        reranked_passages = reranker.rerank(query.question, passages, top_k=10)
        context = build_context(reranked_passages)

        system_prompt = build_system_prompt()
        human_prompt = build_human_prompt(competition["name"], context, query.question)

        for token in llm_interface.generate_response_stream(
            system_prompt, human_prompt
        ):
            token = token.replace("\n", "\\n")
            yield f"data: {token}\n\n"

    except Exception as e:
        logging.error(f"Error processing LLM query: {str(e)}")
        yield f"data: Error: {str(e)}\n\n"
        supabase_manager.update_query(query_id, {"is_success": False})
