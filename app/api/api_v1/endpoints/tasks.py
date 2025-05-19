from fastapi import APIRouter, HTTPException, Depends
from app.tasks.fetch_insert_to_vector_db_tasks import fetch_and_store_threads, fetch_and_store_threads_by_unit, fetch_and_store_threads_by_unit_by_category
from app.tasks.thread_clustering_tasks import cluster_unit_documents
from app.tasks.agents_tasks import run_faq_agent_analysis, run_unit_trend_analysis
from celery import chain
from celery.result import AsyncResult
from celery_worker import app as celery_app
from app.repositories.task_transaction_repository import TaskTransactionRepository
from app.schemas.tasks.requets import RunTaskRequest
from app.core.auth import AuthInfo, get_current_user
from app.api.api_v1.endpoints.units import check_user_unit_access
from app.api import deps
from app import crud
from app.core.config import settings

router = APIRouter()




@router.post("/run_chain/")
async def run_chain_task(request: RunTaskRequest, auth_info: AuthInfo = Depends(get_current_user), db=Depends(deps.get_db)):
    """
    Run a chain of Celery tasks to fetch, cluster, and analyze threads.
    to do validation and error handling
    """
    if not await check_user_unit_access(request.unitId, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")
    repo = TaskTransactionRepository()
    transcation_record = await repo.create_task(task_name=f"generating faq report",
                                                user_id=request.userId,
                                                unit_id=request.unitId,
                                                input=request.model_dump())
    print("transcation_record" + str(transcation_record))
    task_chain = chain(
        fetch_and_store_threads_by_unit.s(
            request.userId, request.unitId, str(transcation_record.id), request.startDate, request.endDate),
        cluster_unit_documents.s(
            request.unitId, request.startDate, request.endDate),
        run_faq_agent_analysis.s(request.startDate, request.endDate)
    )
    # Execute the chain
    result = task_chain.apply_async()

    return {"transactionId": str(transcation_record.id), "status": result.status, "progress": 0}


@router.post("/run_unit_trend_analysis/")
async def trigger_unit_trend_analysis_task(request: RunTaskRequest, db=Depends(deps.get_db)):
    """
    Trigger the Celery task to run unit trend analysis on clustered questions.
    """
    # if not await check_user_unit_access(request.unitId, auth_info.auth_id, db):
        # raise HTTPException(status_code=403, detail="User does not have access to this unit")
    repo = TaskTransactionRepository()
    transcation_record = await repo.create_task(task_name=request.category,
                                                user_id=request.userId,
                                                unit_id=request.unitId,
                                                input=request.model_dump())
    
    task_chain = chain(fetch_and_store_threads_by_unit_by_category.s(unit_id=request.unitId, user_id=request.userId, transaction_id=str(transcation_record.id), category=request.category),
                       cluster_unit_documents.s(request.unitId),
                       run_unit_trend_analysis.s(request.unitId, request.category))
    result = task_chain.apply_async()
    return {"transactionId": str(transcation_record.id), "status": result.status, "progress": 0}


@router.get("/unit_trend_analysis_report/{unit_id}/{category}")
async def get_unit_trend_analysis_report(unit_id: str, category: str, db=Depends(deps.get_db)):
    """
    Get the unit trend analysis report with processed question details.
    Returns the report and a list of questions with their theme, summary, and thread details.
    """
    repo = TaskTransactionRepository()
    task_status_list = await repo.get_task_result_by_unit_id_and_name(unit_id, category)
    
    if not task_status_list:
        raise HTTPException(status_code=404, detail="No tasks found for this unit and category")
    
    # Find the most recent completed task
    completed_tasks = [task for task in task_status_list if task.status == "completed"]
    if not completed_tasks:
        return completed_tasks[-1]
    
    # Get the most recent task
    latest_task = completed_tasks[-1]
    print("latest_task: ", latest_task)
    
    if latest_task.result:
        # Get the unit and its threads
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
            
        # Create a map of thread IDs to their content for quick lookup
        thread_map = {str(thread.id): thread for thread in unit.threads}
        
        # Process the questions from the result
        questions = []
        for cluster in latest_task.result.get("questions", []):
            thread_details = []
            for thread_id in cluster.get("questionIds", []):
                if thread_id in thread_map:
                    thread = thread_map[thread_id]
                    thread_details.append({
                        "id": str(thread.id),
                        "title": thread.title,
                        "content": thread.content,
                        "url": f"{settings.ED_BASE_URL}/courses/{unit_id}/discussion/{str(thread.id)}"
                    })
            
            questions.append({
                "theme": cluster.get("theme", ""),
                "summary": cluster.get("summary", ""),
                "threads": thread_details
            })
        
        print("questions: ", questions)
        latest_task.result.update({"questions": questions})
        return latest_task
    
    return latest_task

@router.get("/status/{transaction_id}")
async def get_transaction_status(transaction_id: str):
    """
    Get the status of a specific transaction.

    Args:
        transaction_id: ID of the transaction to check

    Returns:
        Status of the transaction
    """
    try:
        # Fetch the task status from the database
        repo = TaskTransactionRepository()
        task_status = await repo.get_transaction_by_id(transaction_id)
        if not task_status:
            raise HTTPException(
                status_code=404, detail="Transaction not found")
        if task_status.status == "PENDING":
            progress = 0
        elif task_status.status == "SUCCESS":
            progress = 100
        elif task_status.status == "FAILURE":
            progress = 0
        elif task_status.status == "running fetch_and_store_threads_by_unit":
            progress = 10
        elif task_status.status == "finish clustering":
            progress = 60
        elif task_status.status == "running agent analysis":
            progress = 80
        else:
            progress = 0

        return {
            "transaction_id": transaction_id,
            "status": task_status.status,
            "progress": progress}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching transaction status: {str(e)}"
        )


@router.get("/task/{task_id}")
async def get_task_by_id(task_id: str):
    """
    Get task details by task ID.

    Args:
        task_id: ID of the task to check

    Returns:
        Task details
    """
    try:
        # Fetch task details from the database
        repo = TaskTransactionRepository()
        task_details = await repo.get_transaction_by_id(task_id)
        if not task_details:
            raise HTTPException(
                status_code=404, detail="Task not found")

        return task_details

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching task details: {str(e)}"
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
