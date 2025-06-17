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
from app.schemas.tasks.task_status import TaskStatus

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
    
    # Store the Celery task ID in the transaction record
    repo.update_task_status_sync(
        task_id=str(transcation_record.id),
        status=TaskStatus.PENDING,
        celery_task_id=result.id
    )

    return {"transactionId": str(transcation_record.id), "status": TaskStatus.RECEIVED, "progress": 0, "celeryTaskId": result.id}


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
    print("result: ", result)
    
    # Store the Celery task ID in the transaction record
    repo.update_task_status_sync(
        task_id=str(transcation_record.id),
        status=TaskStatus.PENDING,
        celery_task_id=result.id
    )
    
    return {"transactionId": str(transcation_record.id), "status": TaskStatus.RECEIVED, "progress": 0, "celeryTaskId": result.id}

@router.get("/status/{transaction_id}")
async def get_transaction_status(transaction_id: str):
    """
    Get the status of a specific transaction.

    Args:
        transaction_id: ID of the transaction to check

    Returns:
        Status of the transaction with progress percentage
    """
    try:
        # Fetch the task status from the database
        repo = TaskTransactionRepository()
        task_status = await repo.get_transaction_by_id(transaction_id)
        if not task_status:
            raise HTTPException(
                status_code=404, detail="Transaction not found")

        return {
            "transaction_id": transaction_id,
            "status": task_status.status,
            "progress": task_status.progress,
            "name": task_status.task_name
        }

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


@router.post("/cancel_chain/{transaction_id}")
async def cancel_task_chain(transaction_id: str):
    """
    Cancel a chain of Celery tasks.

    Args:
        transaction_id: ID of the transaction record containing the Celery task ID

    Returns:
        Status of the cancellation attempt
    """
    try:
        # Get the transaction record to find the Celery task ID
        repo = TaskTransactionRepository()
        transaction = await repo.get_transaction_by_id(transaction_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
            
        celery_task_id = transaction.celery_task_id
        if not celery_task_id:
            raise HTTPException(status_code=404, detail="No Celery task ID found for this transaction")

        # Get the parent task
        parent_task = AsyncResult(celery_task_id, app=celery_app)

        # Revoke the parent task
        celery_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')

        # Try to get and cancel child tasks if they exist
        if hasattr(parent_task, 'children'):
            child_tasks = parent_task.children
            if child_tasks:
                for child in child_tasks:
                    if isinstance(child, AsyncResult):
                        celery_app.control.revoke(
                            child.id, terminate=True, signal='SIGTERM')

        # Update transaction status
        repo.update_task_status_sync(
            task_id=transaction_id,
            status=TaskStatus.CANCELLED
        )

        return {
            "transaction_id": transaction_id,
            "celery_task_id": celery_task_id,
            "status": "CANCELLATION_REQUESTED",
            "message": "Task chain cancellation has been requested"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error cancelling task chain: {str(e)}"
        )

@router.get("/unit_analysis_reports/{unit_id}")
async def get_unit_analysis_reports(unit_id: str, db=Depends(deps.get_db)):
    """
    Get all analysis reports for a specific unit.
    Returns a list of all tasks with their results (if any), creation date, status, category, and task ID.
    Excludes tasks with 'generating faq report' in their task_name.
    """
    repo = TaskTransactionRepository()
    task_status_list = await repo.get_analysis_reports_by_unit_id(unit_id)
    
    if not task_status_list:
        raise HTTPException(status_code=404, detail="No tasks found for this unit")
    
    # Format the response
    reports = []
    for task in task_status_list:
        reports.append({
            "task_id": str(task.id),
            "category": task.task_name,  # Using task_name as category
            "created_at": task.created_at,
            "status": task.status,
            "error_message": task.error_message if task.error_message else None
        })
    
    return reports

@router.get("/unit_trend_analysis_report/{task_id}")
async def get_unit_trend_analysis_report(task_id: str, db=Depends(deps.get_db)):
    """
    Get the unit trend analysis report with processed question details using task ID.
    Returns the report and a list of questions with their theme, summary, and thread details.
    """
    repo = TaskTransactionRepository()
    task = await repo.get_transaction_by_id(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task is not completed yet")
    
    if not task.result:
        raise HTTPException(status_code=404, detail="No results found for this task")
    
    # Get the unit and its threads
    unit = await crud.unit.get(db, {"id": int(task.unit_id)})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
        
    # Create a map of thread IDs to their content for quick lookup
    thread_map = {str(thread.id): thread for thread in unit.threads}
    
    # Process the questions from the result
    questions = []
    for cluster in task.result.get("questions", []):
        thread_details = []
        for thread_id in cluster.get("questionIds", []):
            if thread_id in thread_map:
                thread = thread_map[thread_id]
                thread_details.append({
                    "id": str(thread.id),
                    "title": thread.title,
                    "content": thread.content,
                    "url": f"{settings.ED_BASE_URL}/courses/{task.unit_id}/discussion/{str(thread.id)}"
                })
        
        questions.append({
            "theme": cluster.get("theme", ""),
            "summary": cluster.get("summary", ""),
            "threads": thread_details
        })
    
    task.result.update({"questions": questions})
    return task
