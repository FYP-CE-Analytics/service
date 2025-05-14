from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.api import deps
from app.crud import semester
from app.schemas.semester_schedule import SemesterResponse, SemesterCreate

router = APIRouter()

@router.get("/", response_model=List[SemesterResponse])
async def list_semesters(db=Depends(deps.get_db)):
    """
    List all semester schedules
    """
    sems = await semester.get_multi(db)
    return [SemesterResponse.from_model(s) for s in sems]

@router.get("/{semester_id}", response_model=SemesterResponse)
async def get_semester(semester_id: int, db=Depends(deps.get_db)):
    """
    Retrieve a single semester schedule by ID
    """
    sem = await semester.get(db, {"id": semester_id})
    if not sem:
        raise HTTPException(status_code=404, detail=f"Semester with ID {semester_id} not found")
    return SemesterResponse.from_model(sem) 

@router.post("/", response_model=SemesterResponse)
async def create_semester(semester_req: SemesterCreate, db=Depends(deps.get_db)):
    """
    Create a new semester schedule
    """
    return await semester.create(db, semester_req)
