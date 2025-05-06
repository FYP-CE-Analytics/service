from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.core.auth import JWTBearer
from app.schemas.user import UserResponse, UserCreate, UserUpdate
from app import crud
from odmantic.exceptions import DuplicateKeyError
from odmantic import ObjectId


router = APIRouter()


@router.get("/", response_model=UserResponse)
async def get_user(db=Depends(deps.get_db), email: str = None):
    # Simulate a user retrieval
    user = await crud.user.get_user_synced(db, email=email)
    print(user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_model(user)


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


@router.patch("/{user_id}", response_model=UserResponse)
async def path_user_settings(
    user_id: str,
    user_update: UserUpdate,
    db=Depends(deps.get_db),
):
    """
    Set user's units
    """
    # check if ids are from users

    try:
        user = await crud.user.get(db, {"id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        updated_user = await crud.user.update(db, db_obj=user, obj_in=user_update)
        # need to add selected units as unit collections

        return UserResponse.from_model(updated_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
