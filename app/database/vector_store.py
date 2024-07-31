from pinecone import Pinecone
from app.config import Config

class VectorStore:
    def __init__(self):
        self.pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        self.index = self.pc.Index(Config.PINECONE_INDEX_NAME)

    def upsert(self, vectors):
        self.index.upsert(vectors=vectors)

    def delete_by_competition_id(self, competition_id: str):
        # Use query to fetch all vector IDs associated with this competition_id
        # We use a zero vector to match all vectors, and set top_k to a high number
        zero_vector = [0.0] * 1536  # Adjust the dimension based on your embedding size
        response = self.index.query(
            vector=zero_vector,
            filter={"competition_id": competition_id},
            top_k=10000,  # Adjust based on expected maximum number of vectors per competition
            include_metadata=False
        )
        
        # Extract the vector IDs
        vector_ids = [match.id for match in response.matches]

        if not vector_ids:
            print(f"No vectors found for competition {competition_id}")
            return

        # Delete vectors in batches to avoid overwhelming the API
        batch_size = 1000  # Adjust this based on your Pinecone plan limits
        for i in range(0, len(vector_ids), batch_size):
            batch = vector_ids[i:i+batch_size]
            self.index.delete(ids=batch)

        print(f"Deleted {len(vector_ids)} vectors for competition {competition_id}")
        
    def query(self, vector, competition_id, top_k=10):
        return self.index.query(
            vector=vector,
            filter={"competition_id": competition_id},
            top_k=top_k,
            include_metadata=True
        )