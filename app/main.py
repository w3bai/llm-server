from fastapi import FastAPI, HTTPException, Depends, WebSocket, BackgroundTasks
from app.models import CompetitionCreate, CompetitionResponse, Query
from app.data_ingestion.github_loader import GitHubLoader
from app.data_ingestion.web_scraper import WebScraper
from app.data_processing.text_processor import TextProcessor
from app.data_processing.reranker import Reranker
from app.database.vector_store import VectorStore
from app.llm.interface import LLMInterface
from app.database.supabase_utils import supabase_manager
from middleware import verify_api_key
import logging
import asyncio
import json

app = FastAPI()

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

@app.post("/competitions", response_model=CompetitionResponse, dependencies=[Depends(verify_api_key)])
async def create_competition(competition: CompetitionCreate):
    new_competition = supabase_manager.create_competition(
        competition.name, str(competition.github_url), str(competition.docs_url) if competition.docs_url else None
    )
    competition_id = new_competition['id']
    
    # Load and process GitHub data
    github_files = github_loader.get_repo_contents(competition.github_url)
    for file in github_files:
        content = github_loader.get_file_content(file)
        is_code = file.name.endswith(('.sol', '.rs', '.go'))  # Add more extensions as needed
        chunks = text_processor.chunk_text(content, is_code=is_code)
        for i, chunk in enumerate(chunks):
            try:
                tokens = text_processor.estimate_tokens(chunk)
                embedding = text_processor.generate_embedding(chunk)
                logging.info(f"Processing chunk {i} with {tokens} tokens")
                vector_store.upsert([(f"{competition_id}_github_{file.path}_{i}", embedding, {
                    "text": chunk,
                    "source": "github",
                    "path": file.path,
                    "competition_id": competition_id
                })])
            except ValueError as e:
                logging.warning(f"Skipping chunk due to: {str(e)}")

    # Load and process documentation
    if competition.docs_url:
        web_scraper = WebScraper(competition.docs_url, verify_ssl=False)
        docs = await web_scraper.scrape_site()
        for url, page_data in docs.items():
            chunks = text_processor.chunk_text(page_data['content'], is_code=False)
            for i, chunk in enumerate(chunks):
                try:
                    tokens = text_processor.estimate_tokens(chunk)
                    embedding = text_processor.generate_embedding(chunk)
                    logging.info(f"Processing chunk {i} with {tokens} tokens")
                    vector_store.upsert([(f"{competition_id}_doc_{url}_{i}", embedding, {
                        "text": chunk,
                        "source": "documentation",
                        "url": url,
                        "title": page_data['title'],
                        "competition_id": competition_id
                    })])
                except ValueError as e:
                    logging.warning(f"Skipping chunk due to: {str(e)}")

    return CompetitionResponse(**new_competition)

@app.get("/competitions", dependencies=[Depends(verify_api_key)])
async def list_competitions():
    return supabase_manager.list_competitions()

@app.get("/competitions/{competition_id}", response_model=CompetitionResponse, dependencies=[Depends(verify_api_key)])
async def get_competition(competition_id: str):
    competition = supabase_manager.get_competition(competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    return CompetitionResponse(**competition)
    
@app.delete("/competitions/{competition_id}", response_model=dict, dependencies=[Depends(verify_api_key)])
async def delete_competition(competition_id: str):
    deleted = supabase_manager.delete_competition(competition_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Delete associated data from vector store
    vector_store.delete_by_competition_id(competition_id)
    
    return {"message": f"Competition {competition_id} has been deleted"}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections[client_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except:
        del active_connections[client_id]
        
@app.post("/query", dependencies=[Depends(verify_api_key)])
async def query(query: Query, background_tasks: BackgroundTasks):
    competition = supabase_manager.get_competition(query.competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    # Start the LLM query process in the background
    background_tasks.add_task(process_llm_query, competition, query)

    return {"message": "Query processing started", "status": "pending"}

async def process_llm_query(competition, query):
    try:
        question_embedding = text_processor.generate_embedding(query.question)
        results = vector_store.query(question_embedding, competition['id'], top_k=50)
        
        if not results or not hasattr(results, 'matches') or len(results.matches) == 0:
            logging.warning("No results found in vector store")
            await send_websocket_message(query.client_id, {"error": "No results found in vector store"})
            return

        passages = [match.metadata['text'] for match in results.matches if 'text' in match.metadata]
        reranked_passages = reranker.rerank(query.question, passages, top_k=10)
        context = "\n\n".join([f"Content: {passage}" for passage in reranked_passages])

        system_prompt = """You are an AI assistant designed to help security researchers and answer their questions about this audit contest."""

        human_prompt = f"""Your responses should be based solely on the following context:
'{competition['name']}' context
{context}

Your task is to answer questions about this audit contest using only the information provided in the context above. Follow these guidelines:

1. Draw your responses exclusively from the provided context.
2. Keep your answers concise and to the point.
3. Do not speculate or provide information beyond what is explicitly stated in the context.
4. Provide code snippets whenever necessary. Make sure each codeblock is on a new line.
5. If you cannot answer a question based on the given context, state that you don't have enough information to answer.
6. Use js instead of solidity in codeblocks for highlighting purposes
7. Do not mention 'context' in your response

Scope: Only the files explicitly outlined in the Scope section of the context are considered in scope. Do not reference or use information from any other sources.

When answering, format your response as follows:
1. Begin with a brief, direct answer to the question
2. Break down the answer into clear, numbered steps.
3. Provide:
- A detailed explanation of what needs to be done
- The specific function or method to be used, if applicable
- A code snippet or function signature, where relevant
4. If necessary, provide additional context or explanation from the given information.

Here is the question to answer:

{query.question}

"""
        response = llm_interface.generate_response(system_prompt, human_prompt)

        # Send the response back through the WebSocket
        await send_websocket_message(query.client_id, {"response": response, "query_id": query.query_id})

    except Exception as e:
        logging.error(f"Error processing LLM query: {str(e)}")
        await send_websocket_message(query.client_id, {"error": str(e), "query_id": query.query_id})

async def send_websocket_message(client_id, message):
    print(f"client_id: {client_id}")
    if client_id in active_connections:
        print(f"client id: {client_id} is in active_connections: {active_connections}")
        print(f"message: {message}")
        await active_connections[client_id].send_text(json.dumps(message))
