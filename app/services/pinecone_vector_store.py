from app.interfaces.vector_store_interface import VectorStoreBase
from pinecone import Pinecone, Index
from app.schemas.vector_store import VectorSearchResponse, DeleteResponse, UpsertResponse
from typing import List


class PineconeVectorStore(VectorStoreBase):
    """Pinecone vector store implementation."""

    def __init__(self, index_name: str, namespace: str, api_key: str = None):
        self.pc_service = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.namespace = namespace
        self.index: Index = None
        self._connect()

    def _connect(self):
        """Connect to the Pinecone index."""
        if not self.pc_service.has_index(self.index_name):
            self.pc_service.create_index_for_model(
                name=self.index_name,
                cloud="aws",
                region="us-east-1",
                embed={
                    "model": "llama-text-embed-v2",
                    "field_map": {"text": "content"}
                }
            )
        self.index = self.pc_service.Index(self.index_name)

    def search_with_string(self, query_string, collection_name, top_k=3, threshold=None, **kwargs) -> VectorSearchResponse:

        response = self.index.search(namespace=collection_name, query={
            "inputs": {"text": query_string},
            "top_k": top_k,
        }, fields=["id", "content", "metadata"], rerank={
            "model": "cohere-rerank-3.5",
            "rank_fields": ["content"]})
        hits = response.get("result", {}).get("hits", [])
        if threshold is not None:
            hits = [hit for hit in hits if hit.get("_score", 0) > threshold]
        return VectorSearchResponse(hits=hits, total=len(hits))

    def search_with_vector(self, vector: List[int], collection_name, top_k=3, threshold=None, **kwargs) -> VectorSearchResponse:
        response = self.index.query(namespace=collection_name,
                                    vector=vector, top_k=top_k, fields=["id", "content", "metadata"], rerank={
                                        "model": "cohere-rerank-3.5",
                                        "rank_fields": ["content"]})
        hits = response.get("result", {}).get("hits", [])
        if threshold is not None:
            hits = [hit for hit in hits if hit.get("_score", 0) > threshold]
        return VectorSearchResponse(hits=hits, total=len(hits))

    def upsert(self, content, collection_name, pre_embedded=False, **kwargs):
        if pre_embedded:
            self.vectorstore.upsert(vectors=content, namespace=collection_name)

        response = self.vectorstore.upsert_records(
            records=content, namespace=collection_name)
        if response.get("error"):
            return UpsertResponse(error=response.get("error"))
        return UpsertResponse(upserted_count=len(content), error=response.get("error"))

    def delete(self, ids: List[str], collection_name, **kwargs) -> DeleteResponse:
        raise NotImplementedError(
            "Delete operation is not supported in Pinecone vector store.")

    def get_embedding(self, text):
        return super().get_embedding(text)
