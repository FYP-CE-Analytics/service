from typing import Dict, List, Any, Optional
from celery_worker import app
from app.services.crewai_service import UnitFAQCrewService, UnitTrendAnalysisCrewService    
from app.const import VECTOR_INDEX_NAME
from app.schemas.crewai_faq_service_schema import CrewAIFAQInputSchema, CrewAIUnitTrendAnalysisInputSchema
from app.schemas.tasks.cluster_schema import ClusterTaskResult, CoreDocument
from app.repositories.task_transaction_repository import TaskTransactionRepository
from pymongo import MongoClient
import os
from app.utils.shared import parse_date
from app.utils.cluster_utils import create_question_clusters
from app.db.session import get_sync_client
from app.utils.shared import is_within_interval

# Get a direct connection to MongoDB
client = MongoClient(os.getenv("MONGO_DATABASE_URI"))
db = client[os.getenv('DB_NAME', 'ed_summarizer')]

# Initialize repositories
task_repo = TaskTransactionRepository()


@app.task(bind=True, name="run_faq_agent_analysis")
def run_faq_agent_analysis(self, clustering_result: dict = None, start_date=None, end_date=None, cluster_id: str = None, unit_id: str = None) -> Dict[str, Any]:
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
        task_id=transaction_id,
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

    # Extract clustered questions from the core docs
    core_clustered_docs: List[CoreDocument] = clustering_result.result.core_docs
    core_clustered_content = [
        {"id": doc.id, "metadata": doc.metadata.model_dump(mode='json')}
        for doc in core_clustered_docs
    ]
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
    unit_data = db.unit.find_one({"_id": int(unit_id)}, {"weeks": 1, "name": 1, "description": 1, "content": 1})
    # assign the weeks list from the document
    weeks = unit_data.get("weeks", [])
    selected_week = next((week for week in weeks if is_within_interval(start_date, week.get("start_date"), week.get("end_date"))), None)
    print("unit info", unit_data.get("name", ""), unit_data.get("description", ""))
    # Prepare input for the crew service
    input_data = {
        "unit_id": unit_id,
        "unit_name": unit_data.get("name", "") + " " + unit_data.get("description", ""),
        "questions": core_clustered_content,
        "content": unit_data.get("content", ""),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "week": selected_week.get("week_id"),
        "weekly_content": selected_week.get("content"),
    }

    # Update task state
    self.update_state(state="PROCESSING",
                      meta={"status": "Running agent analysis", "unit_id": unit_id})

    result = UnitFAQCrewService(
        index_name=VECTOR_INDEX_NAME).run(CrewAIFAQInputSchema(**input_data))
    
    print("agent analysis result", result)
    # Update transaction with result
    task_repo.update_task_status_sync(
        task_id=transaction_id,
        status="completed",
        result=result.model_dump()
    )

    ## insert into question cluster
    question_clusters = create_question_clusters(
        result.model_dump(), 
        unit_id, 
        transaction_id, 
        input_data.get("start_date"), 
        input_data.get("end_date"), 
        input_data.get("weeks", [])  # Ensure weeks is passed as a list
    )
    
    # Convert QuestionClusterModel instances to dictionaries, ensuring _id is handled
    cluster_dicts = [cluster.model_dump(by_alias=True) for cluster in question_clusters]
    
    # Use the sync client obtained from session.py
    sync_client = get_sync_client()
    collection = sync_client["question_cluster"]
    
    # For each cluster, either update existing or insert new
    for cluster_dict in cluster_dicts:
        # Check if cluster exists (using theme, unit_id, and date range)
        existing = collection.find_one({
            "theme": cluster_dict["theme"],
            "unit_id": cluster_dict["unit_id"],
            "weekStart": cluster_dict["weekStart"],
            "weekEnd": cluster_dict["weekEnd"]
        })
        
        if existing:
            # Update existing cluster
            collection.update_one(
                {"_id": existing["_id"]},
                {"$set": cluster_dict}
            )
        else:
            # Insert new cluster
            collection.insert_one(cluster_dict)

    # Return result with transaction_id for chaining
    return {
        "status": "success",
        "message": "Agent analysis completed successfully",
        "unit_id": unit_id,
        "result": result.model_dump(),
        "transaction_id": transaction_id
    }

@app.task(bind=True, name="run_unit_trend_analysis")
def run_unit_trend_analysis(self, clustering_result: dict = None, unit_id: str = None, category: str = None) -> Dict[str, Any]:
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
        task_id=transaction_id,
        status="running unit trend analysis",
    )

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

    # Extract clustered questions from the core docs
    core_clustered_docs: List[CoreDocument] = clustering_result.result.core_docs
    core_clustered_content = [
        {"id": doc.id, "metadata": doc.metadata.model_dump(mode='json')}
        for doc in core_clustered_docs
    ]
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
    unit_data = db.unit.find_one({"_id": int(unit_id)})

    if not unit_data:
        return {
            "status": "error",
            "message": f"Unit data not found for unit_id: {unit_id}",
            "unit_id": unit_id
        }


    # Prepare input for the crew service
    input_data = {
        "unit_id": unit_id,
        "unit_name": unit_data.get("name", "") + " " + unit_data.get("description", ""),
        "questions": core_clustered_content,
        "content": unit_data.get("content", ""),
        "category": category,
        "assessment_description": "assignment",
    }

    # Update task state
    self.update_state(state="PROCESSING",
                      meta={"status": "Running agent analysis", "unit_id": unit_id})

    result = UnitTrendAnalysisCrewService(
        index_name=VECTOR_INDEX_NAME).run(CrewAIUnitTrendAnalysisInputSchema(**input_data))
    
    print("agent analysis result", result)
    # Update transaction with result
    task_repo.update_task_status_sync(
        task_id=transaction_id,
        status="completed",
        result=result.model_dump()
    )

    # Return result with transaction_id for chaining
    return {
        "status": "success",
        "message": "Agent analysis completed successfully",
        "unit_id": unit_id,
        "result": result.model_dump(),
        "transaction_id": transaction_id
    }
    
