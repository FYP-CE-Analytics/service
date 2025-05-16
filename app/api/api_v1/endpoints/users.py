from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.core.auth import JWTBearer, get_current_user, AuthInfo
from app.schemas.user import UserResponse, UserCreate, UserUpdate, UserUpdateSelectedUnits, UserCreateReq
from app import crud
from odmantic.exceptions import DuplicateKeyError


router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    auth_info: AuthInfo = Depends(get_current_user),
    db = Depends(deps.get_db)
):
    """
    Get current user information including selected, available, and previous units
    """
    print("auth_info", auth_info)
    user =await crud.user.sync_user_units(db, auth_info.auth_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserResponse)
async def create_user(
    user: UserCreateReq,
    auth_info: AuthInfo = Depends(get_current_user),
    db = Depends(deps.get_db)
):
    try:
        # Check if user already exists
        existing_user = await crud.user.get(db, {"auth_id": auth_info.auth_id})
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="User already exists"
            )
        
        # Create user with auth info
        create_user = UserCreate(
            auth_id=auth_info.auth_id,
            email=user.email,
            name=user.name,
            api_key=user.api_key
        )
        print("user", create_user)
        user_res = await crud.user.create(db, obj_in=create_user)
        return user_res
    except DuplicateKeyError as e:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists.",
        )


@router.patch("/me", response_model=UserResponse)
async def update_user_settings(
    user_update: UserUpdate,
    auth_info: AuthInfo = Depends(get_current_user),
    db = Depends(deps.get_db)
):
    """
    Update user settings and handle unit creation for selected units
    """
    try:
        user = await crud.user.get(db, {"auth_id": auth_info.auth_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Update user
        updated_user = await crud.user.update(db, db_obj=user, obj_in=user_update)
        user_synced = await crud.user.sync_user_units(db, auth_info.auth_id)
        return UserResponse.from_model(user_synced)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/me/selected-units", response_model=UserResponse)
async def update_user_selected_units(
    user_update: UserUpdateSelectedUnits,
    auth_info: AuthInfo = Depends(get_current_user),
    db = Depends(deps.get_db)
):
    user = await crud.user.get(db, {"auth_id": auth_info.auth_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    updated_user = await crud.user.update_selected_units(db, str(user.id), user_update.selected_units)
    return UserResponse.from_model(updated_user)
 
        
