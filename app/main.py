from fastapi import FastAPI, HTTPException
from app.models import CompetitionCreate, CompetitionResponse, Query
from app.competition.manager import CompetitionManager
from app.data_ingestion.github_loader import GitHubLoader
from app.data_ingestion.web_scraper import WebScraper
from app.data_processing.text_processor import TextProcessor
from app.database.vector_store import VectorStore
from app.llm.interface import LLMInterface
import logging

app = FastAPI()

competition_manager = CompetitionManager()
github_loader = GitHubLoader()
text_processor = TextProcessor()
vector_store = VectorStore()
llm_interface = LLMInterface()

@app.post("/competitions", response_model=CompetitionResponse)
async def create_competition(competition: CompetitionCreate):
    competition_id = competition_manager.create_competition(
        competition.name, str(competition.github_url), str(competition.docs_url) if competition.docs_url else None
    )
    
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
        web_scraper = WebScraper(competition.docs_url, verify_ssl=False)  # Set verify_ssl to False
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

    created_competition = competition_manager.get_competition(competition_id)
    return CompetitionResponse(
        id=created_competition.id,
        name=created_competition.name,
        github_url=created_competition.github_url,
        docs_url=created_competition.docs_url,
        created_at=created_competition.created_at
    )

@app.get("/competitions")
async def list_competitions():
    return competition_manager.list_competitions()

@app.delete("/competitions/{competition_id}", response_model=dict)
async def delete_competition(competition_id: str):
    deleted = competition_manager.delete_competition(competition_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Delete associated data from vector store
    vector_store.delete_by_competition_id(competition_id)
    
    return {"message": f"Competition {competition_id} has been deleted"}


@app.post("/query")
async def query(query: Query):
    competition = competition_manager.get_competition(query.competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    question_embedding = text_processor.generate_embedding(query.question)
    results = vector_store.query(question_embedding, competition.id, top_k=20)

    if not results or not hasattr(results, 'matches'):
        raise HTTPException(status_code=500, detail="No results found in vector store")

    # Extract and rank context
    context_parts = []
    for match in results.matches:
        if hasattr(match, 'metadata') and 'text' in match.metadata:
            context_parts.append({
                'text': match.metadata['text'],
                'score': match.score,
                'source': match.metadata.get('source', 'Unknown'),
                'path': match.metadata.get('path', 'Unknown')
            })

    # Sort by score and take top 10
    context_parts = sorted(context_parts, key=lambda x: x['score'], reverse=True)[:10]

    context = "\n\n".join([f"Source: {part['source']}, Path: {part['path']}\nContent: {part['text']}" for part in context_parts])

    system_prompt = """You are an AI assistant meant to answer questions about audit contests. Draw your responses from the provided context only. Keep answers concise. Do not speculate. Synthesize information from multiple sources when necessary. If no question is present, response with 'No question is present. Please ask a question.'. """

    human_prompt = f"""Context for competition '{competition.name}':
{context}

Question: {query.question}

Please provide a detailed and structured response. Include the following in your answer:
1. A clear and concise summary of the main points.
2. Specific details from the context, citing sources when possible.
3. Any relevant connections or implications not explicitly stated but can be reasonably inferred.
4. If certain information is missing or unclear, state this explicitly.

Organize your response in a logical manner, using numbered or bulleted lists where appropriate."""

    response = llm_interface.generate_response(system_prompt, human_prompt)

    return {"response": response}