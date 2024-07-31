from pinecone import Pinecone, ServerlessSpec
from app.config import Config

def setup_pinecone_index():
    pc = Pinecone(api_key=Config.PINECONE_API_KEY)

    if Config.PINECONE_INDEX_NAME not in pc.list_indexes().names():
        print(f"Creating index: {Config.PINECONE_INDEX_NAME}")
        pc.create_index(
            name=Config.PINECONE_INDEX_NAME,
            dimension=1536,  # Dimension for text-embedding-3-small
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        print("Index created successfully")
    else:
        print(f"Index {Config.PINECONE_INDEX_NAME} already exists")

if __name__ == "__main__":
    setup_pinecone_index()
