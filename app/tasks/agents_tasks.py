from app.tasks.thread_clustering_tasks import cluster_unit_documents
from celery import chain
from typing import Dict, List, Any, Optional
from datetime import datetime
from celery_worker import app
from app.services.crewai_service import UnitAnalysisCrewService
from app.const import VECTOR_INDEX_NAME
from app.schemas.crewai_faq_service_schema import CrewAIFAQInputSchema
from bson import ObjectId
from app.db.session import MongoDatabase
from app.schemas.tasks.cluster_schema import ClusterTaskResult, CoreDocument
from app.repositories.task_transaction_repository import TaskTransactionRepository


@app.task(bind=True, name="run_agent_analysis")
def run_agent_analysis(self, clustering_result: dict = None, cluster_id: str = None, unit_id: str = None) -> Dict[str, Any]:
    """
    Celery task to run agent analysis on clustered questions.
    This task can be chained with the cluster_unit_documents task or run independently with a cluster_id.

    Args:
        clustering_result: Optional result dictionary from the cluster_unit_documents task
        cluster_id: Optional cluster ID to retrieve results from database directly
        unit_id: Optional unit ID (required if cluster_id is provided)

    Returns:
        Dictionary with agent analysis results
    """
    task_repo = TaskTransactionRepository()

    transaction_id = clustering_result.get("transaction_id")
    task_repo.update_task_status_sync(
        id=transaction_id,
        status="running agent analysis",
    )
    print(
        f"Running agent analysis with clustering_result: {clustering_result}, cluster_id: {cluster_id}, unit_id: {unit_id}")
    # # Determine cluster_id and unit_id from either the clustering_result or provided params
    if clustering_result is not None:
        clustering_result = ClusterTaskResult(**clustering_result)

    # Determine cluster_id and unit_id from either the clustering_result or provided params
    if clustering_result and clustering_result.status == "error":
        return clustering_result.dict()
    if clustering_result:
        cluster_id = clustering_result.result.cluster_id
        unit_id = clustering_result.result.unit_id

    # Update task state
    self.update_state(state="PROCESSING",
                      meta={"status": "Retrieving clustered questions", "unit_id": unit_id})

    # if not cluster_doc:
    #     return {
    #         "status": "error",
    #         "message": f"Cluster with ID {cluster_id} not found",
    #         "unit_id": unit_id
    #     }

    # Extract clustered questions from the core docs
    core_clustered_docs: List[CoreDocument] = clustering_result.result.core_docs
    core_clustered_content = [doc.metadata.model_dump(mode='json')
                              for doc in core_clustered_docs]

    print(core_clustered_content)
    if not core_clustered_docs:
        return {
            "status": "warning",
            "message": "No clustered questions found to analyze",
            "unit_id": unit_id
        }

    # Fetch unit metadata
    self.update_state(state="PROCESSING",
                      meta={"status": "Fetching unit data", "unit_id": unit_id})

    # Use the session to fetch unit data
    # To do
    # unit_data = db.units.find_one({"unit_id": unit_id})
    # if not unit_data:
    #     return {
    #         "status": "error",
    #         "message": f"Unit data not found for unit_id: {unit_id}",
    #         "unit_id": unit_id
    #     }

    # Prepare input for the crew service
    input_data = {
        "unit_id": unit_id,
        "unit_name": "Network and Security",
        "questions": core_clustered_content,
        "content": "Networking is the practice of connecting computers and other devices together to share resources. It involves the use of hardware and software to create a network that allows devices to communicate with each other. Networking is essential for modern computing, as it enables users to access the internet, share files, and collaborate on projects. There are many different types of networks, including local area networks (LANs), wide area networks (WANs), and wireless networks. Each type of network has its own unique characteristics and uses."
    }

    # Update task state
    self.update_state(state="PROCESSING",
                      meta={"status": "Running agent analysis", "unit_id": unit_id})

    result = UnitAnalysisCrewService(
        index_name=VECTOR_INDEX_NAME).run(CrewAIFAQInputSchema(**input_data)).model_dump()
    task_repo.update_task_status_sync(
        id=transaction_id,
        status="completed",
        result=result
    )
    return {
        "status": "success",
        "message": "Agent analysis completed successfully",
        "unit_id": unit_id,
        "result": result
    }


def start_clustering_and_agent_analysis(unit_id: str, auto_optimize: bool = True):
    """
Helper function to start the clustering and agent analysis chain
"""
    task_chain = chain(
        cluster_unit_documents.s(unit_id, auto_optimize=auto_optimize),
        run_agent_analysis.s()
    )

    return task_chain()


def start_agent_analysis(cluster_id: str, unit_id: str):
    """
    Helper function to start agent analysis directly with a known cluster_id
    """
    return run_agent_analysis.delay(cluster_id=cluster_id, unit_id=unit_id)
