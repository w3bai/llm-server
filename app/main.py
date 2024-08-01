from fastapi import FastAPI, HTTPException
from app.models import CompetitionCreate, CompetitionResponse, Query
from app.competition.manager import CompetitionManager
from app.data_ingestion.github_loader import GitHubLoader
from app.data_ingestion.web_scraper import WebScraper
from app.data_processing.text_processor import TextProcessor
from app.data_processing.reranker import Reranker
from app.database.vector_store import VectorStore
from app.llm.interface import LLMInterface
import logging

app = FastAPI()

competition_manager = CompetitionManager()
github_loader = GitHubLoader()
text_processor = TextProcessor()
vector_store = VectorStore()
llm_interface = LLMInterface()
reranker = Reranker()

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

@app.get("/competitions/{competition_id}", response_model=CompetitionResponse)
async def get_competition(competition_id: str):
    competition = competition_manager.get_competition(competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    return CompetitionResponse(
        id=competition.id,
        name=competition.name,
        github_url=competition.github_url,
        docs_url=competition.docs_url,
        created_at=competition.created_at
    )
    
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

    logging.info(f"Generating embedding for question: {query.question}")
    question_embedding = text_processor.generate_embedding(query.question)

    logging.info(f"Querying vector store for competition_id: {competition.id}")
    results = vector_store.query(question_embedding, competition.id, top_k=50)
    logging.info(f"Query results: {results}")

    if not results or not hasattr(results, 'matches') or len(results.matches) == 0:
        logging.warning("No results found in vector store")
        raise HTTPException(status_code=500, detail="No results found in vector store")

    # Extract passages for reranking
    passages = [match.metadata['text'] for match in results.matches if 'text' in match.metadata]
    
    # Rerank passages
    reranked_passages = reranker.rerank(query.question, passages, top_k=10)

    # Create context from reranked passages
    context = "\n\n".join([f"Content: {passage}" for passage in reranked_passages])

    system_prompt = """You are an AI assistant specializing in explaining technical processes in blockchain systems and smart contracts. Your responses should be detailed, precise, and focus on practical implementation. Always provide step-by-step explanations, include relevant code snippets or function signatures, and highlight any important considerations or potential issues."""

    human_prompt = f"""Context for competition '{competition.name}':
{context}

Question: {query.question}

Please provide a comprehensive and technically precise answer. Your response should:

1. Start with a brief overview of the process or concept being asked about.
2. Break down the answer into clear, numbered steps.
3. For each step, provide:
- A detailed explanation of what needs to be done
- The specific function or method to be used, if applicable
- A code snippet or function signature, where relevant
4. If relevant, explain how this process fits into the larger system architecture.
5. Conclude with any final considerations or next steps.

Use markdown formatting for code snippets, replace solidity with js in the codeblock for highlighting purposes. If any part of the question cannot be answered based on the provided context, clearly state that. Base your entire response solely on the information provided in the context."""

    response = llm_interface.generate_response(system_prompt, human_prompt, model=query.model)

    return {"response": response, "model_used": query.model}
