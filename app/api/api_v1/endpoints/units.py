from fastapi import APIRouter, Depends, HTTPException, Query
from app.api import deps
from app.schemas.unit import UnitResponse, UpdateUnitRequest
from app import crud
from app.services.ed_forum_service import get_ed_service
from odmantic import ObjectId
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from app.repositories.question_cluster_repository import QuestionClusterRepository
from app.utils.shared import is_within_interval, parse_date
from app.models.unit_dashboard import ThreadMetadata, UnitModel
from app.repositories.task_transaction_repository import TaskTransactionRepository
from app.core.auth import AuthInfo, get_current_user


router = APIRouter()
cluster_repo = QuestionClusterRepository()


@router.get("/{unit_id}", response_model=UnitResponse)
async def get_user_unit_detail(unit_id: str, db=Depends(deps.get_db), auth_info: AuthInfo = Depends(get_current_user)):
    """
    Get user's unit detail
    """
    if not await check_user_unit_access(unit_id, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")

    # Avoid double try-except by handling common errors directly
    unit = await crud.unit.get(db, {"id": int(unit_id)})

    if not unit:
        raise HTTPException(
            status_code=404, detail=f"Unit with ID {unit_id} not found")

    return UnitResponse.from_model(unit)


@router.patch("/{unit_id}")
async def update_unit(unit_id: int, unit_update: UpdateUnitRequest, db=Depends(deps.get_db), auth_info: AuthInfo = Depends(get_current_user)):
    """
    Update unit details
    """
    if not await check_user_unit_access(unit_id, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")
    try:
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        updated_unit = await crud.unit.update(db=db, db_obj=unit, obj_in=unit_update)
        return UnitResponse.from_model(updated_unit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/{course_id}/unanswered-threads")
async def get_unanswered_threads(course_id: int, db=Depends(deps.get_db), auth_info: AuthInfo = Depends(get_current_user)):
    if not await check_user_unit_access(course_id, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")
    user = await crud.user.get(db, {"auth_id": auth_info.auth_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ed_service = await get_ed_service(user.api_key)
    threads = await ed_service.get_unanswered_threads(course_id)
    return threads

# @router.get("/{course_id}/all-threads")
# async def get_all_threads(course_id: int, db=Depends(deps.get_db)):
#     # if not await check_user_unit_access(course_id, auth_info.auth_id, db):
#     #     raise HTTPException(status_code=403, detail="User does not have access to this unit")
#     # user = await crud.user.get(db, {"auth_id": auth_info.auth_id})
#     # if not user:
#     #     raise HTTPException(status_code=404, detail="User not found")
#     ed_service = await get_ed_service("z1vssi.9KlxOrzubW93NZi5VYrsFdwccfJ1Koqnu9fxt0Or")
#     threads = await ed_service.get_all_students_threads(course_id)
#     return threads

async def create_thread_metadata(thread: Dict[str, Any], theme_lookup: Dict[str, List[str]]) -> ThreadMetadata:
    """Create ThreadMetadata object from thread data"""
    return ThreadMetadata(
        id=str(thread["id"]),
        title=thread["title"],
        content=thread["document"],
        created_at=thread["created_at"],
        updated_at=thread["updated_at"],
        is_answered=thread["is_answered"],
        is_student_answered=thread["is_student_answered"],
        is_staff_answered=thread["is_staff_answered"],
        needs_attention=False,
        themes=theme_lookup.get(str(thread["id"]), []),
        last_sync_at=datetime.now().isoformat(),
        vote_count=thread["vote_count"],
        thread_type=thread["type"],
        category=thread.get("subcategory") or thread.get("category", "uncategorized"),
        user_role=thread.get("user_role", "anonymous")
    )

async def update_existing_thread(existing_thread: ThreadMetadata, thread: Dict[str, Any], theme_lookup: Dict[str, List[str]]) -> bool:
    """Update existing thread if there are changes"""
    has_changes = False
    
    # Update themes if available
    if str(thread["id"]) in theme_lookup:
        existing_thread.themes.extend(theme_lookup[str(thread["id"])])
        existing_thread.themes = list(set(existing_thread.themes))
        has_changes = True

    # Check for other changes
    if (existing_thread.updated_at != thread["updated_at"] or
        existing_thread.content != thread["document"] or
        existing_thread.title != thread["title"]):
        
        existing_thread.title = thread["title"]
        existing_thread.content = thread["document"]
        existing_thread.updated_at = thread["updated_at"]
        existing_thread.is_answered = thread["is_answered"]
        existing_thread.is_student_answered = thread["is_student_answered"]
        existing_thread.is_staff_answered = thread["is_staff_answered"]
        existing_thread.vote_count = thread["vote_count"]
        existing_thread.thread_type = thread["type"]
        existing_thread.category = thread.get("subcategory") or thread.get("category", "uncategorized")
        existing_thread.last_sync_at = datetime.now().isoformat()
        has_changes = True

    return has_changes

async def update_week_statistics(unit: UnitModel):
    """Update thread counts and category counts for each week"""
    for week in unit.weeks:
        # Get threads for this week
        week_threads = [
            t for t in unit.threads 
            if is_within_interval(t.created_at, week.start_date, week.end_date)
        ]
        week.thread_count = len(week_threads)
        
        # Calculate category counts
        week_category_counts = {}
        for thread in week_threads:
            category = thread.category or 'uncategorized'
            week_category_counts[category] = week_category_counts.get(category, 0) + 1
        
        week.category_counts = week_category_counts

@router.post("/{unit_id}/sync-threads")
async def sync_unit_threads(
    unit_id: str,
    auth_info: AuthInfo = Depends(get_current_user),
    db=Depends(deps.get_db)
):
    """
    Sync all threads from Ed service to local database for a specific unit
    Filters out social categories and handles duplicates
    """
    # Check access and get unit
    if not await check_user_unit_access(unit_id, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")
    
    unit = await crud.unit.get(db, {"id": int(unit_id)})
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit with ID {unit_id} not found")

    # Get Ed service
    user = await crud.user.get(db, {"auth_id": auth_info.auth_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    ed_service = await get_ed_service(user.api_key)
    
    # Fetch threads and clusters
    threads = await ed_service.get_all_students_threads(course_id=int(unit_id))
    clusters = await cluster_repo.get_clusters_by_date_range(None, None, unit_id)
    
    # Create theme lookup
    theme_lookup = {}
    for cluster in clusters:
        for qid in cluster.question_ids:
            if qid not in theme_lookup:
                theme_lookup[qid] = []
            theme_lookup[qid].append(cluster.theme)

    # Process threads
    existing_thread_ids = {thread.id for thread in unit.threads}
    new_threads = []
    updated_threads = []
    skipped_count = 0

    for thread in threads:
        # Skip social categories
        if thread.get("category", "").lower() == "social":
            skipped_count += 1
            continue

        if str(thread["id"]) in existing_thread_ids:
            # Update existing thread
            for existing_thread in unit.threads:
                if existing_thread.id == str(thread["id"]):
                    if await update_existing_thread(existing_thread, thread, theme_lookup):
                        updated_threads.append(existing_thread)
                    break
        else:
            # Add new thread
            thread_meta = await create_thread_metadata(thread, theme_lookup)
            new_threads.append(thread_meta)

    # Update unit
    unit.threads.extend(new_threads)
    unit.last_sync_at = datetime.now().isoformat()
    unit.thread_count = len(unit.threads)
    
    # Update week statistics
    await update_week_statistics(unit)
    
    # Save changes
    await crud.unit.engine.save(unit)
    
    return {
        "status": "success",
        "message": "Sync completed",
        "stats": {
            "total_threads": len(unit.threads),
            "new_threads": len(new_threads),
            "updated_threads": len(updated_threads),
            "skipped": skipped_count
        }
    }

@router.get("/{unit_id}/threads")
async def get_unit_threads(
    unit_id: str,
    auth_info: AuthInfo = Depends(get_current_user),
    start_date: str = None,
    end_date: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    theme: str = None,
    is_answered: bool = None,
    db=Depends(deps.get_db)
):
    """
    Get all threads for a unit with pagination and filtering
    """

    if not await check_user_unit_access(unit_id, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")
    try:
        # Get unit
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail=f"Unit with ID {unit_id} not found")

        # Themes are synced during sync_unit_threads; skip cluster lookup here

        # Filter and paginate threads
        filtered_threads = unit.threads

        # Apply filters
        if start_date:
            filtered_threads = [t for t in filtered_threads if t.created_at >= parse_date(start_date)]
        if end_date:
            filtered_threads = [t for t in filtered_threads if t.created_at <= parse_date(end_date)]
        if theme:
            filtered_threads = [t for t in filtered_threads if theme in t.themes]
        if is_answered is not None:
            filtered_threads = [t for t in filtered_threads if t.is_answered == is_answered]

        # Calculate pagination
        total_threads = len(filtered_threads)
        total_pages = (total_threads + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_threads)

        # Get paginated threads
        paginated_threads = filtered_threads[start_idx:end_idx]

        # Prepare response threads with pre-synced themes
        enriched_threads = [thread.model_dump() for thread in paginated_threads]

        return {
            "unit_id": unit.id,
            "unit_name": unit.name,
            "threads": enriched_threads,
            "pagination": {
                "total": total_threads,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/{unit_id}/weeks")
async def get_unit_weeks(
    unit_id: str,
    db=Depends(deps.get_db),
    auth_info: AuthInfo = Depends(get_current_user)
):
    """
    Get weeks data for a unit with updated thread counts.
    Thread counts are updated for the current week only.
    Returns weeks data matching WeekConfig interface and transaction data.
    """
    if not await check_user_unit_access(unit_id, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")
    try:
        # Get unit
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail=f"Unit with ID {unit_id} not found")

        # Initialize task transaction repository
        task_repo = TaskTransactionRepository()

        # Get all tasks for this unit
        tasks = await task_repo.get_tasks_by_unit_id(unit_id)

        # Process each week
        weeks_data = []
        for week in unit.weeks:
            # Format week data according to WeekConfig interface
            week_data = {
                "weekId": week.week_id,
                "teachingWeekNumber": week.teaching_week_number,
                "weekType": week.week_type,
                "startDate": week.start_date,
                "endDate": week.end_date,
                "content": week.content,
                "threadCount": week.thread_count,
                "faqReports": [task for task in tasks if (task.task_name.lower().startswith("generating faq report") and
                    is_within_interval(task.input.get("startDate"), week.start_date, week.end_date))],
                "categoryCounts": week.category_counts
                
                }
            weeks_data.append(week_data)

        return {
            "unit_id": unit.id,
            "unit_name": unit.name,
            "weeks": weeks_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{unit_id}/categories")
async def get_unit_categories(unit_id: str, db=Depends(deps.get_db))->List[str]:
    unit = await crud.unit.get(db, {"id": int(unit_id)})
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit with ID {unit_id} not found")
    return list(set([t.category for t in unit.threads]))

async def check_user_unit_access(unit_id: str, auth_id: str, db=Depends(deps.get_db))->bool:
    user = await crud.user.get(db, {"auth_id": auth_id})
    print("user", user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return list(filter(lambda x: x.id == int(unit_id), user.available_units)) or list(filter(lambda x: x.id == int(unit_id), user.selected_units))