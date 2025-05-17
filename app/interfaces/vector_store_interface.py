from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union

# Import the response types
from app.schemas.vector_store import VectorSearchResponse, DeleteResponse, UpsertResponse


class VectorStoreBase(ABC):
    """Abstract base class for vector store operations."""

    @abstractmethod
    def search_with_string(
        self,
        query_string: str,
        collection_name: str,
        top_k: int = 3,
        threshold: Optional[float] = None,
        filter: Optional[dict] = None,
        **kwargs: Any
    ) -> VectorSearchResponse:
        """
        Searches the vector store for similar vectors using a query string.

        If 'embedding' is provided, it will use that directly.
        If not, the implementation should generate the embedding from the query_string.

        Args:
            query_string: The query string to search for.
            collection_name: The specific collection or namespace to search within.
            top_k: The number of top results to return.
            threshold: An optional score threshold to filter results.
            **kwargs: Additional provider-specific arguments.

        Returns:
            VectorSearchResponse object with search hits and metadata.
        """
        pass

    @abstractmethod
    def search_with_vector(
        self,
        vector: List[float],
        collection_name: str,
        top_k: int = 3,
        threshold: Optional[float] = None,
        **kwargs: Any
    ) -> VectorSearchResponse:
        """
        Searches the vector store using a pre-computed embedding vector.

        Args:
            vector: The embedding vector to search with.
            collection_name: The specific collection or namespace to search within.
            top_k: The number of top results to return.
            threshold: An optional score threshold to filter results.
            **kwargs: Additional provider-specific arguments.

        Returns:
            VectorSearchResponse object with search hits and metadata.
        """
        pass

    @abstractmethod
    def upsert(
        self,
        content: List[Dict[str, Any]],
        collection_name: str,
        pre_embedded: bool = False,
        **kwargs: Any
    ) -> UpsertResponse:
        """
        Upserts content into the specified collection.

        If 'pre_embedded' is False, each item in 'content' should have at least 'id' and 'content' keys.
        The 'content' field will be used to generate the embedding.

        If 'pre_embedded' is True, each item should have 'id', 'vector' (the embedding), and optionally 'metadata'.

        Args:
            content: A list of dictionaries with item data. Each dictionary must include:
                    - 'id': unique identifier
                    - Either 'content' (text to embed) or 'vector' (if pre_embedded=True)
                    - Optional additional fields will be stored as metadata
            collection_name: The collection/namespace to upsert into.
            pre_embedded: Whether the items in 'content' already contain embedding vectors.
            **kwargs: Additional provider-specific arguments.

        Returns:
            UpsertResponse with the number of successfully upserted items.
        """
        pass

    @abstractmethod
    def delete(self, ids: List[str], collection_name: str, **kwargs: Any) -> DeleteResponse:
        """
        Deletes vectors by ID from the specified collection.

        Args:
            ids: List of IDs to delete.
            collection_name: The collection/namespace to delete from.
            **kwargs: Additional provider-specific arguments.

        Returns:
            DeleteResponse with information about the deletion operation.
        """
        pass

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding for the given text.

        This method may be called directly or used internally by search_with_string
        and upsert methods when embeddings aren't provided.

        Args:
            text: The text to generate an embedding for.

        Returns:
            A list of floats representing the embedding vector.
        """
        pass
