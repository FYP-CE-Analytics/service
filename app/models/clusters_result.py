from odmantic import Field, EmbeddedModel, Model
from datetime import datetime


class DocumentClusterModel(EmbeddedModel):
    id: str = Field()
    cluster: int = Field()
    content: str = Field()
    category: str = Field()


class ClusterParametersModel(EmbeddedModel):
    min_cluster_size: int = Field(default=5)
    min_samples: int = Field(default=5)
    metric: str = Field(default="cosine")


class ClusterResultModel(Model):
    unit_id: int = Field()
    created_at: datetime = Field(default_factory=datetime.now)
    num_documents: int = Field(default=0)
    num_clusters: int = Field(default=0)
    parameters: ClusterParametersModel = Field(default={})
    core_docs: list[DocumentClusterModel] = Field(
        default_factory=list)
