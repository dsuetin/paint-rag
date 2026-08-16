from pydantic import BaseModel

from paint_rag.rag.documents import Chunk
from paint_rag.rag.embeddings import EmbeddingModel
from paint_rag.rag.vector_store import VectorStore


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float


class Retriever:

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_model: EmbeddingModel,
    ):
        self.vector_store = vector_store
        self.embedding_model = embedding_model

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:

        query_vector = (
            self.embedding_model.embed_query(
                query
            )
        )

        results = self.vector_store.search(
            query_vector,
            top_k=top_k,
        )

        return [
            RetrievedChunk(
                chunk=chunk,
                score=score,
            )
            for chunk, score in results
        ]