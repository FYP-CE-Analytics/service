from fastapi import APIRouter, Depends, HTTPException
from app.api import deps
from app.schemas.unit import UnitResponse, UpdateUnitRequest
from app import crud

router = APIRouter()


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
        return updated_unit
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
