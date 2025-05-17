from fastapi import APIRouter, HTTPException, Depends, Query
from app.repositories.question_cluster_repository import QuestionClusterRepository
from app.repositories.task_transaction_repository import TaskTransactionRepository
from app.services.ed_forum_service import get_ed_service
from app.utils.shared import parse_date
from fastapi import Depends
from app.core.config import settings
from app.api import deps
from odmantic import AIOEngine
from app import crud
from app.core.auth import AuthInfo, get_current_user
from app.api.api_v1.endpoints.units import check_user_unit_access

router = APIRouter()
cluster_repo = QuestionClusterRepository()
task_repo = TaskTransactionRepository()


@router.get("/units/{unit_id}/clusters")
async def get_unit_clusters(
    unit_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    auth_info: AuthInfo = Depends(get_current_user),
    db: AIOEngine = Depends(deps.get_db)
):
    """
    Get all question clusters for a specific unit with pagination.
    Includes thread content from unit.threads and handles threads that belong to multiple themes.
    """
    if not await check_user_unit_access(unit_id, auth_info.auth_id, db):
        raise HTTPException(status_code=403, detail="User does not have access to this unit")
    # Get the unit to access thread content
    unit = await crud.unit.get(db, {"id": int(unit_id)})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    # Get all clusters for the unit
    clusters = await cluster_repo.get_clusters_by_unit_id(unit_id)

    # Create a map of thread IDs to their content for quick lookup
    thread_map = {thread.id: thread for thread in unit.threads}

    # Process clusters and their questions
    processed_clusters = []
    for cluster in clusters:
        questions = []
        for thread_id in cluster.question_ids:
            if thread_id in thread_map:
                thread = thread_map[thread_id]
                questions.append({
                    "id": thread.id,
                    "content": thread.content,
                    "title": thread.title,
                    "is_answered": thread.is_answered,
                    "needs_attention": thread.needs_attention,
                    "vote_count": thread.vote_count,
                    "url": f"{settings.ED_BASE_URL}/courses/{unit_id}/discussion/{thread_id}"
                })

        processed_clusters.append({
            "theme": cluster.theme,
            "summary": cluster.summary,
            "questions": questions,
            "weekStart": cluster.weekStart,
            "weekEnd": cluster.weekEnd,
            "unitId": cluster.unit_id,
            "transactionIds": cluster.transaction_ids,
            "metadata": cluster.metadata,
            "weekConfig": {
                "weekId": next((week.week_id for week in unit.weeks if week.start_date.strftime("%Y-%m-%d") == cluster.weekStart), None),
                "weekNumber": next((week.teaching_week_number for week in unit.weeks if week.start_date.strftime("%Y-%m-%d") == cluster.weekStart), None),
                "weekType": next((week.week_type for week in unit.weeks if week.start_date.strftime("%Y-%m-%d") == cluster.weekStart), None)
            }
        })

    # Implement pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_clusters = processed_clusters[start_idx:end_idx]

    return {
        "unitId": unit_id,
        "clusters": paginated_clusters,
        "pagination": {
            "current_page": page,
            "page_size": page_size,
            "total_clusters": len(processed_clusters),
            "total_pages": (len(processed_clusters) + page_size - 1) // page_size
        }
    }



