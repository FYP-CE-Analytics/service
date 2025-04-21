from fastapi import APIRouter
from app.tasks.fetch_insert_to_vector_db_tasks import fetch_and_store_threads
from app.tasks.thread_clustering_tasks import cluster_unit_documents
router = APIRouter()


@router.post("/insert")
async def trigger_vector_insertion_task():
    """
    Trigger the Celery task to fetch and store threads in the vector database.
    """
    # Call the Celery task
    result = fetch_and_store_threads.delay()
    return {"task_id": result.id, "status": result.status}


@router.post("/cluster/{unit_id}")
async def trigger_clustering_task(unit_id: str):
    """
    Trigger the Celery task to fetch and store threads in the vector database.
    """
    # Call the Celery task
    res = cluster_unit_documents.delay(unit_id)
    return {"task_id": res.id, "status": res.status}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of a Celery task.
    """
    # Check the status of the task
    result = fetch_and_store_threads.AsyncResult(task_id)
    if result.state == 'PENDING':
        # Task is still in progress
        return {"task_id": task_id, "status": "PENDING"}
    elif result.state == 'SUCCESS':
        # Task completed successfully
        return {"task_id": task_id, "status": "SUCCESS", "result": result.result}
    elif result.state == 'FAILURE':
        # Task failed
        return {"task_id": task_id, "status": "FAILURE", "error": str(result.info)}
    else:
        # Task is in some other state
        return {"task_id": task_id, "status": result.state}
