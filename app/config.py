import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    API_KEY = os.getenv("API_KEY")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    PINECONE_INDEX_NAME = "web3-audit-assistant"
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    GITHUB_RELEVANT_EXTENSIONS = (
        ".sol",
        ".go",
        ".rs",
        ".md",
        ".txt",
        ".yml",
        ".yaml",
        ".sw",
    )
    GITHUB_IGNORE_DIRECTORIES = (
        "test",
        "tests",
        "lib",
        "libs",
        "node_modules",
        "build",
        "dist",
    )
    GITHUB_INCLUDE_DIRECTORIES = (
        "src",
        "contracts",
        "",
    )  # Empty string for root directory
