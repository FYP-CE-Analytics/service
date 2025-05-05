from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.core.auth import JWTBearer
from app.schemas.user import UserResponse, UserCreate, UserEdCoursesResponse, UnitIdsUpdate, UserUpdate, UnitSyncInfo
from app import crud
from odmantic.exceptions import DuplicateKeyError
from app.services.ed_forum_service import EdService
from odmantic import ObjectId
from app.schemas.unit import UpdateUnitRequest
router = APIRouter()


@router.get("/", response_model=UserResponse)
async def get_user(db=Depends(deps.get_db), email: str = None):
    # Simulate a user retrieval
    user = await crud.user.get(db, {"email": email})
    print(user.selected_units)
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


@router.get("/units", response_model=UserEdCoursesResponse)
async def get_users_units(email: str, ed_service: EdService = Depends(deps.get_user_ed_service), db=Depends(deps.get_db)):
    """
    Get user's active courses
    """
    try:
        courses = await ed_service.get_user_active_courses()

        for course in courses:
            print(course)
            await crud.unit.create(db, obj_in=course)
        return UserEdCoursesResponse(active=courses)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/units", response_model=UserResponse)
async def set_user_units(
    id: ObjectId,
    unit_ids: UnitIdsUpdate,
    db=Depends(deps.get_db),

):
    """
    Set user's units
    """
    # check if ids are from users

    try:
        user = await crud.user.get(db, {"id": id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        updated_units = []
        for unit_id in unit_ids.selectedUnitIds:
            if unit_id in user.selected_units:
                updated_units.append(user.selected_units[unit_id])
            else:
                updated_units.append(UnitSyncInfo(unit_id=unit_id))

        update_data = UserUpdate(
            selected_units=updated_units,
        )

        updated_user = await crud.user.update(db, db_obj=user, obj_in=update_data)

        print(updated_user)
        return UserResponse.from_model(updated_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/units/{unit_id}")
async def get_user_unit_detail(unit_id: int, db=Depends(deps.get_db)):
    """
    Get user's unit detail
    """
    try:
        unit = await crud.unit.get(db, {"id": int(unit_id)})
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        return unit
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/units/{unit_id}")
async def set_user_unit_detail(unit_id, unit_info: UpdateUnitRequest, db=Depends(deps.get_db)):
    """
    Set user's unit detail
    """
    try:
        unit = await crud.unit.get(db, {"id": int(unit_id)})

        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")

        updated_unit = await crud.unit.update(db, db_obj=unit, obj_in=unit_info)
        return updated_unit
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
