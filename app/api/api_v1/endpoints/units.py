from fastapi import APIRouter, Depends, HTTPException, Query
from app.api import deps
from app.schemas.unit import UnitResponse, UpdateUnitRequest
from app import crud
from app.services.ed_forum_service import get_ed_service
from odmantic import ObjectId
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.repositories.question_cluster_repository import QuestionClusterRepository
from app.utils.shared import parse_date
from app.models.unit_dashboard import ThreadMetadata
from app.db.session import get_engine

router = APIRouter()
cluster_repo = QuestionClusterRepository(engine=get_engine())


@router.get("/{unit_id}", response_model=UnitResponse)
async def get_user_unit_detail(unit_id: str, db=Depends(deps.get_db)):
    """
    Get user's unit detail
    """
    # Avoid double try-except by handling common errors directly
    unit = await crud.unit.get(db, {"id": int(unit_id)})
    print(unit)

    if not unit:
        raise HTTPException(
            status_code=404, detail=f"Unit with ID {unit_id} not found")

    return UnitResponse.from_model(unit)


@router.patch("/{unit_id}")
async def update_unit(unit_id: int, unit_update: UpdateUnitRequest, db=Depends(deps.get_db)):
    """
    Update unit details
    """
    try:
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        updated_unit = await crud.unit.update(db=db, db_obj=unit, obj_in=unit_update)
        return UnitResponse.from_model(updated_unit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/{course_id}/unanswered-threads")
async def get_unanswered_threads(user_id, course_id: int, db=Depends(deps.get_db)):
    user = await crud.user.get(db, {"id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ed_service = await get_ed_service(user.api_key)
    threads = await ed_service.get_unanswered_threads(course_id)
    return threads


@router.post("/{unit_id}/sync-threads")
async def sync_unit_threads(
    unit_id: str,
    user_id: str,
    db=Depends(deps.get_db)
):
    """
    Sync all threads from Ed service to local database for a specific unit
    Filters out social categories and handles duplicates
    """
    try:
        # Get unit
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail=f"Unit with ID {unit_id} not found")

        # Get user's Ed service
        user = await crud.user.get(db, {"id": ObjectId(user_id)})
        print(user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        ed_service = await get_ed_service(user.api_key)
        
        # Fetch all threads from Ed
        threads = ed_service.client.list_all_students_threads(course_id=int(unit_id))
        print(threads)
        # Create a set of existing thread IDs for quick lookup
        existing_thread_ids = {thread.id for thread in unit.threads}
        
        # Process threads and update unit
        new_threads = []
        updated_threads = []
        
        for thread in threads:
            # Skip social categories
            if thread.category.lower() == "social":
                continue
                
            # Create thread metadata
            thread_meta = ThreadMetadata(
                id=str(thread.id),
                title=thread.title,
                content=thread.document,
                created_at=thread.created_at.isoformat(),
                updated_at=thread.updated_at.isoformat(),
                is_answered=thread.vote_count > 0,  # Consider answered if has votes
                needs_attention=False,  # Default to False, can be set based on business logic
                themes=[thread.category, thread.subcategory, thread.subsubcategory],
                last_sync_at=datetime.now().isoformat(),
                # Additional metadata
                unique_views=thread.unique_view_count,
                vote_count=thread.vote_count,
                thread_type=thread.type,
                category=thread.category,
                subcategory=thread.subcategory,
                subsubcategory=thread.subsubcategory,
                user_id=thread.user_id
            )
            
            # Check if thread already exists
            if thread.id in existing_thread_ids:
                # Update existing thread
                for existing_thread in unit.threads:
                    if existing_thread.id == str(thread.id):
                        # Update only if there are changes
                        if (existing_thread.updated_at != thread.updated_at or
                            existing_thread.content != thread.document or
                            existing_thread.title != thread.title):
                            # Update basic fields
                            existing_thread.title = thread.title
                            existing_thread.content = thread.document
                            existing_thread.updated_at = thread.updated_at
                            existing_thread.is_answered = thread.vote_count > 0
                            
                            # Update metadata fields
                            existing_thread.unique_views = thread.unique_view_count
                            existing_thread.vote_count = thread.vote_count
                            existing_thread.thread_type = thread.type
                            existing_thread.category = thread.category
                            existing_thread.subcategory = thread.subcategory
                            existing_thread.subsubcategory = thread.subsubcategory
                            existing_thread.user_id = thread.user_id
                            
                            existing_thread.last_sync_at = datetime.now()
                            updated_threads.append(existing_thread)
                        break
            else:
                # Add new thread
                new_threads.append(thread_meta)
        
        # Update unit with new and updated threads
        unit.threads.extend(new_threads)
        unit.last_sync_at = datetime.now().isoformat()
        unit.thread_count = len(unit.threads)

        await crud.unit.engine.save(unit)
        
        return {
            "status": "success",
            "message": f"Sync completed",
            "stats": {
                "total_threads": len(unit.threads),
                "new_threads": len(new_threads),
                "updated_threads": len(updated_threads),
                "skipped_social": len([t for t in threads if t.category.lower() == "social"])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{unit_id}/threads")
async def get_unit_threads(
    unit_id: str,
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
    try:
        # Get unit
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail=f"Unit with ID {unit_id} not found")

        # Get clusters for this unit
        clusters = await cluster_repo.get_clusters_by_date_range(
            parse_date(start_date) if start_date else None,
            parse_date(end_date) if end_date else None,
            unit_id
        )

        # Create theme lookup from clusters
        theme_lookup = {}
        for cluster in clusters:
            for qid in cluster.question_ids:
                if qid not in theme_lookup:
                    theme_lookup[qid] = []
                theme_lookup[qid].append(cluster.theme)

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

        # Enrich threads with cluster themes
        enriched_threads = []
        for thread in paginated_threads:
            thread_dict = thread.model_dump()
            # Add themes from clusters
            if thread.id in theme_lookup:
                thread_dict["themes"].extend(theme_lookup[thread.id])
                thread_dict["themes"] = list(set(thread_dict["themes"]))  # Remove duplicates
            enriched_threads.append(thread_dict)

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


