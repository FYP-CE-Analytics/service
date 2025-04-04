from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.core.auth import JWTBearer
from app.schemas.user import UserResponse, UserCreate, UserEdCoursesResponse, UnitIdsUpdate
from app import crud
from odmantic.exceptions import DuplicateKeyError
from app.services.ed_forum_service import EdService

router = APIRouter()


@router.get("/", response_model=UserResponse)
async def get_user(db=Depends(deps.get_db), email: str = None):
    # Simulate a user retrieval
    user = await crud.user.get_user_by_email(db=db, email=email)
    print(user)
    return user


@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db=Depends(deps.get_db)):
    try:
        user_res = await crud.user.create(db, obj_in=user)
        return user_res
    except DuplicateKeyError as e:
        print(e)
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists.",
        )


@router.get("/units", response_model=UserEdCoursesResponse)
async def get_users_units(email: str, ed_service: EdService = Depends(deps.get_user_ed_service)):
    """
    Get user's active courses
    """
    try:
        courses = await ed_service.get_user_active_courses()
        return UserEdCoursesResponse(active=courses)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/units", response_model=UserResponse)
async def set_user_units(
    email: str,
    unit_ids: UnitIdsUpdate,
    db=Depends(deps.get_db),

):
    """
    Set user's units
    """
    # check if ids are from users

    try:
        user = await crud.user.get_user_by_email(db, email=email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.selected_unit_ids = unit_ids
        await crud.user.update(db, db_obj=user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
