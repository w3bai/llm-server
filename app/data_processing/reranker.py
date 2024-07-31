from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, model_name='cross-encoder/ms-marco-MiniLM-L-6-v2'):
        self.model = CrossEncoder(model_name)

    def rerank(self, query, passages, top_k=5):
        pairs = [[query, passage] for passage in passages]
        scores = self.model.predict(pairs)

        # Create a list of (score, index) tuples
        scored_results = list(enumerate(scores))
        
        # Sort by score in descending order
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        # Return the top_k results
        top_results = scored_results[:top_k]
        
        return [passages[idx] for idx, _ in top_results]