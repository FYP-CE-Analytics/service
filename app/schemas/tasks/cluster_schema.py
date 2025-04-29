from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.schemas.tasks.base_task_result_schema import TaskResult


class ClusteringParameters(BaseModel):
    """Schema for clustering parameters"""
    auto_optimized: bool = Field(
        default=True, description="Whether parameters were automatically optimized")
    min_cluster_size: int = Field(...,
                                  description="Minimum size of clusters for HDBSCAN")
    min_samples: int = Field(...,
                             description="Minimum samples parameter for HDBSCAN")
    metric: str = Field(..., description="Distance metric used for clustering")


class DocMetadata(BaseModel):
    """Schema for document metadata"""
    content: str = Field(..., description="Text content of the document")
    category: str = Field(..., description="Category of the document")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last updated timestamp")
    additional_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if isinstance(v, datetime) else v
        }
    )


class CoreDocument(BaseModel):
    """Schema for a core document representing a cluster"""
    id: str = Field(..., description="Document ID")
    probability: float = Field(...,
                               description="Probability score from HDBSCAN")
    metadata: DocMetadata = Field(..., description="Document metadata")

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if isinstance(v, datetime) else v
        }
    )


class ClusterAnalysisInput(BaseModel):
    """Schema for input to the agent analysis task"""
    cluster_id: Optional[str] = Field(
        None, description="ID of the cluster to analyze")
    unit_id: str = Field(..., description="Unit ID")
    status: Optional[str] = Field(
        None, description="Status from previous task if in a chain")


# For database storage of cluster records
class ClusterRecord(BaseModel):
    """Schema for cluster records stored in MongoDB"""
    unit_id: str = Field(..., description="Unit ID that was processed")
    created_at: datetime = Field(default_factory=datetime.now)
    num_documents: int = Field(...,
                               description="Number of documents processed")
    num_clusters: int = Field(..., description="Number of clusters found")
    parameters: ClusteringParameters = Field(...,
                                             description="Parameters used for clustering")
    core_docs: List[CoreDocument] = Field(
        ..., description="Core documents for each cluster")
    cluster_id: Optional[str] = Field(
        None, description="Unique identifier for the cluster")


ClusterTaskResult = TaskResult[ClusterRecord]
