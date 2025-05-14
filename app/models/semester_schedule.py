from odmantic import Field, Model, EmbeddedModel
from datetime import datetime
from enum import Enum
from typing import List
from pydantic import field_validator


class SemesterPhaseType(str, Enum):
    """
    Enumeration of possible phases in an academic semester.
    """
    TEACHING_PERIOD = "teaching_period"
    MIDSEM_BREAK = "mid_semester_break"
    TEACHING_WEEKS_FINISH = "teaching_weeks_finish"
    SWOT_VAC = "swot_vac"
    FINAL_ASSESSMENTS = "final_assessments"


class SemesterPhase(EmbeddedModel):
    """
    Represents a specific phase within a semester (e.g., teaching period, mid-semester break).
    """
    type: SemesterPhaseType = Field(...)
    start_date: datetime = Field(...)
    end_date: datetime = Field(...)


class SemesterModel(Model):
    """
    Model representing an academic semester schedule with its various date ranges.
    """
    id: int = Field(primary_field=True)
    year: int = Field(...)
    semester: int = Field(...)  # 1 or 2
    phases: List[SemesterPhase] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("updated_at")
    def set_updated_at(cls, v):
        """Ensure updated_at is set to now on creation/update if not provided."""
        return v or datetime.now()

    def add_phase(self, phase: SemesterPhase) -> None:
        """
        Add a new phase or update an existing one in the semester schedule.
        """
        for idx, existing in enumerate(self.phases):
            if existing.type == phase.type:
                self.phases[idx] = phase
                return
        self.phases.append(phase) 