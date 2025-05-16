from fastapi import APIRouter

from app.api.api_v1.endpoints import users, tasks, units, question_cluster_routes, semesters

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(units.router, prefix="/units", tags=["units"])
api_router.include_router(question_cluster_routes.router, prefix="/question-clusters", tags=["question-clusters"])
api_router.include_router(semesters.router, prefix="/semesters", tags=["semesters"])
