from pydantic import BaseModel, Field


class RunTaskRequest(BaseModel):
    """
    Schema for the request to run a task.
    """
    unitId: str = Field(..., description="ID of the unit to process")
    userId: str = Field(...,
                        description="ID of the user who initiated the task")
    startDate: str = Field(...,
                           description="Start date for the task in YYYY-MM-DD format")
    endDate: str = Field(...,
                         description="End date for the task in YYYY-MM-DD format")
