from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class VectorSearchHit(BaseModel):
    """Represents a single hit/result from a vector search."""
    id: str = Field(description="The unique identifier of the document")
    score: float = Field(
        description="The similarity score or relevance score (higher is better)")
    content: str = Field(description="The textual content of the document")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata associated with the document")


class VectorSearchResponse(BaseModel):
    """Represents the response from a vector search operation."""
    hits: List[VectorSearchHit] = Field(
        default_factory=list, description="The search results/hits")
    total: int = Field(
        default=0, description="The total number of hits found (may be more than returned)")
    error: Optional[str] = Field(
        default=None, description="Error message if the search failed")

    def is_empty(self) -> bool:
        """Returns True if no hits were found."""
        return len(self.hits) == 0

    def is_error(self) -> bool:
        """Returns True if the search resulted in an error."""
        return self.error is not None

    @classmethod
    def error_response(cls, error_message: str) -> "VectorSearchResponse":
        """Creates an error response with the given error message."""
        return cls(error=error_message)


class DeleteResponse(BaseModel):
    """Response model for a vector deletion operation."""
    deleted_count: int = Field(
        default=0, description="The number of vectors successfully deleted")
    error: Optional[str] = Field(
        default=None, description="Error message if the deletion failed")

    def is_error(self) -> bool:
        """Returns True if the deletion resulted in an error."""
        return self.error is not None

    @classmethod
    def error_response(cls, error_message: str) -> "DeleteResponse":
        """Creates an error response with the given error message."""
        return cls(error=error_message)


class UpsertResponse(BaseModel):
    """Response model for a vector upsert operation."""
    upserted_count: int = Field(
        default=0, description="The number of vectors successfully upserted")
    error: Optional[str] = Field(
        default=None, description="Error message if the upsert failed")

    def is_error(self) -> bool:
        """Returns True if the upsert resulted in an error."""
        return self.error is not None

    @classmethod
    def error_response(cls, error_message: str) -> "UpsertResponse":
        """Creates an error response with the given error message."""
        return cls(error=error_message)
