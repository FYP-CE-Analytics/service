from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.core.auth import JWTBearer
from app.schemas.user import UserResponse, UserCreate, UserUpdate, UserUpdateSelectedUnits
from app import crud
from odmantic.exceptions import DuplicateKeyError
from odmantic import ObjectId
from app.models.unit_dashboard import UnitStatus
from typing import List, Set


router = APIRouter()


@router.get("/", response_model=UserResponse)
async def get_user(db=Depends(deps.get_db), email: str = None):
    """
    Get user information including selected, available, and previous units
    """
    try:
        # Get user with basic info
        user = await crud.user.get(db, {"email": email.lower()})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        print(user)

        previous_units = await crud.unit.get_multi(
            db,
            {
                "id": {"$in": [unit.id for unit in user.previous_units]},
                "status": UnitStatus.PAST
            }
        )

        user.previous_units = [unit.model_dump() for unit in previous_units]
        return user.model_dump()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
async def update_user_settings(
    user_id: str,
    user_update: UserUpdate,
    db=Depends(deps.get_db),
):
    """
    Update user settings and handle unit creation for selected units
    """
    try:
        # Get user
        user = await crud.user.get(db, {"id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user
        updated_user = await crud.user.update(db, db_obj=user, obj_in=user_update)
        return UserResponse.from_model(updated_user)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{user_id}/selected-units", response_model=UserResponse)
async def update_user_selected_units(
    user_id: str,
    user_update: UserUpdateSelectedUnits,
    db=Depends(deps.get_db),
):
    print("user_update", user_update)
    updated_user = await crud.user.update_selected_units(db, user_id, user_update.selected_units)
    return UserResponse.from_model(updated_user)
 
        
