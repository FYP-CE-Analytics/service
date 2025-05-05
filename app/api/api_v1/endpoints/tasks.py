from fastapi import APIRouter, HTTPException
from app.tasks.fetch_insert_to_vector_db_tasks import fetch_and_store_threads, fetch_and_store_threads_by_unit
from app.tasks.thread_clustering_tasks import cluster_unit_documents
from app.tasks.agents_tasks import run_agent_analysis
from celery import chain
from celery.result import AsyncResult
from celery_worker import app as celery_app
from app.repositories.task_transaction_repository import TaskTransactionRepository
from app.schemas.tasks.requets import RunTaskRequest

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


@router.post("/run_agent_analysis")
async def trigger_agent_analysis_task(unit_id: str, cluster_id: str):
    """
    Trigger the Celery task to run agent analysis on clustered questions.
    """
    # Call the Celery task
    res = run_agent_analysis.delay(unit_id, cluster_id)


@router.post("/run_chain/")
async def run_chain_task(request: RunTaskRequest):
    """
    Run a chain of Celery tasks to fetch, cluster, and analyze threads.
    to do validation and error handling
    """
    repo = TaskTransactionRepository()
    transcation_record = await repo.create_task(task_name="run_chain_task",
                                                user_id=request.userId,
                                                unit_id=request.unitId,
                                                input=request.model_dump())
    print("transcation_record" + str(transcation_record))
    task_chain = chain(
        fetch_and_store_threads_by_unit.s(
            request.userId, request.unitId, str(transcation_record.id), request.startDate, request.endDate),
        cluster_unit_documents.s(
            request.unitId, request.startDate, request.endDate),
        run_agent_analysis.s(request.startDate, request.endDate)
    )
    # Execute the chain
    result = task_chain.apply_async()

    return {"transactionId": str(transcation_record.id), "status": result.status}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of a Celery task.

    Args:
        task_id: ID of the task to check

    Returns:
        Current status and result/error if available
    """
    try:
        # Get task result using the task_id
        result = AsyncResult(task_id, app=celery_app)

        response = {
            "task_id": task_id,
            "status": result.state
        }

        # Add more details based on the state
        if result.state == 'SUCCESS':
            # Include the task result
            response["result"] = result.result
        elif result.state == 'FAILURE':
            # Include the error information
            response["error"] = str(
                result.info) if result.info else "Unknown error"
        elif result.state == 'REVOKED':
            response["message"] = "Task was cancelled"
        elif result.state in ['STARTED', 'PROGRESS']:
            # Include progress information if available
            if isinstance(result.info, dict) and 'current' in result.info and 'total' in result.info:
                response["progress"] = {
                    "current": result.info['current'],
                    "total": result.info['total'],
                    "percent": int((result.info['current'] / result.info['total']) * 100)
                }

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking task status: {str(e)}"
        )


@router.get("/{unit_id}")
async def get_unit_tasks(unit_id: str):
    """
    Get all tasks related to a specific unit.

    Args:
        unit_id: ID of the unit to check

    Returns:
        List of task IDs related to the unit
    """
    try:
        # Fetch tasks from the database
        repo = TaskTransactionRepository()
        tasks = await repo.get_tasks_by_unit_id(unit_id)
        return tasks

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching tasks for unit {unit_id}: {str(e)}"
        )


@router.post("/cancel_chain/{chain_id}")
async def cancel_task_chain(chain_id: str):
    """
    Cancel a chain of Celery tasks.

    Args:
        chain_id: ID of the chain's parent task

    Returns:
        Status of the cancellation attempt
    """
    try:
        # Get the parent task
        parent_task = AsyncResult(chain_id, app=celery_app)

        # Revoke the parent task
        celery_app.control.revoke(chain_id, terminate=True, signal='SIGTERM')

        # Try to get and cancel child tasks if they exist
        # Note: This depends on how your chain was created and if children are tracked
        if hasattr(parent_task, 'children'):
            child_tasks = parent_task.children
            if child_tasks:
                for child in child_tasks:
                    if isinstance(child, AsyncResult):
                        celery_app.control.revoke(
                            child.id, terminate=True, signal='SIGTERM')

        return {
            "chain_id": chain_id,
            "status": "CANCELLATION_REQUESTED",
            "message": "Task chain cancellation has been requested"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error cancelling task chain: {str(e)}"
        )
