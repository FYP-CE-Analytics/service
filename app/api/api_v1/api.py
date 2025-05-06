from fastapi import APIRouter

from app.api.api_v1.endpoints import users, tasks, units

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(units.router, prefix="/units", tags=["units"])
