from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.api import deps
from app.crud import semester
from app.schemas.semester_schedule import SemesterResponse, SemesterCreate
from app.models.semester_schedule import SemesterPhase, SemesterPhaseType
from datetime import datetime

router = APIRouter()

@router.get("/")
async def list_semesters(db=Depends(deps.get_db)):
    """
    List all semester schedules
    """
    semesters = [
                {
                    "id": 1,
                    "year": 2024,
                    "semester": 1,
                    "phases": [
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2024, 2, 26), end_date=datetime(2024, 5, 24)),
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2024, 4, 1), end_date=datetime(2024, 4, 5)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2024, 5, 27), end_date=datetime(2024, 5, 31)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2024, 6, 3), end_date=datetime(2024, 6, 21))
                    ]
                },
                {
                    "id": 2,
                    "year": 2024,
                    "semester": 2,
                    "phases": [
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2024, 7, 22), end_date=datetime(2024, 10, 18)),
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2024, 9, 23), end_date=datetime(2024, 9, 27)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2024, 10, 21), end_date=datetime(2024, 10, 25)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2024, 10, 28), end_date=datetime(2024, 11, 15))
                    ]
                },
                {
                    "id": 3,
                    "year": 2025,
                    "semester": 1,
                    "phases": [
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2025, 3, 3), end_date=datetime(2025, 6, 1)),
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2025, 4, 21), end_date=datetime(2025, 4, 27)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2025, 6, 2), end_date=datetime(2025, 6, 8)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2025, 6, 9), end_date=datetime(2025, 6, 27))
                    ]
                },
                {
                    "id": 4,
                    "year": 2025,
                    "semester": 2,
                    "phases": [
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2025, 7, 28), end_date=datetime(2025, 10, 26)),
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2025, 9, 29), end_date=datetime(2025, 10, 5)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2025, 10, 27), end_date=datetime(2025, 11, 2)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2025, 11, 3), end_date=datetime(2025, 11, 19))
                    ]
                },
                {
                    "id": 5,
                    "year": 2026,
                    "semester": 1,
                    "phases": [
                        
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2026, 3, 2), end_date=datetime(2026, 5,31 )),#TEACHING PERIODS  finish before swot vac
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2026, 4, 6), end_date=datetime(2026, 4, 12)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2026, 6, 1), end_date=datetime(2026, 6, 7)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2026, 6, 8), end_date=datetime(2026, 6, 26))
                    ]
                },
                {
                    "id": 6,
                    "year": 2026,
                    "semester": 2,
                    "phases": [
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2026, 7, 27), end_date=datetime(2026, 10, 25)),
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2026, 9, 28), end_date=datetime(2026, 10, 4)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2026, 10, 26), end_date=datetime(2026, 11, 1)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2026, 11, 2), end_date=datetime(2026, 11, 20))
                    ]
                },
                {
                    "id": 7,
                    "year": 2027,
                    "semester": 1,
                    "phases": [
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2027, 3, 1), end_date=datetime(2027, 5, 30)),
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2027, 3, 29), end_date=datetime(2027, 4, 4)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2027, 5, 31), end_date=datetime(2027, 6, 6)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2027, 6, 7), end_date=datetime(2027, 6, 25))
                    ]
                },
                {
                    "id": 8,
                    "year": 2027,
                    "semester": 2,
                    "phases": [
                        SemesterPhase(type=SemesterPhaseType.TEACHING_PERIOD, start_date=datetime(2027, 7, 26), end_date=datetime(2027, 10, 24)),
                        SemesterPhase(type=SemesterPhaseType.MIDSEM_BREAK, start_date=datetime(2027, 9, 27), end_date=datetime(2027, 10, 3)),
                        SemesterPhase(type=SemesterPhaseType.SWOT_VAC, start_date=datetime(2027, 10, 25), end_date=datetime(2027, 11, 1)),
                        SemesterPhase(type=SemesterPhaseType.FINAL_ASSESSMENTS, start_date=datetime(2027, 11, 1), end_date=datetime(2027, 11, 19))
                    ]
                }
            ]
    return semesters