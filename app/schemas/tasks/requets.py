from pydantic import BaseModel, Field


class RunTaskRequest(BaseModel):
    """
    Schema for the request to run a task.
    """
    unitId: str = Field(..., description="ID of the unit to process")
    userId: str = Field(...,
                        description="ID of the user who initiated the task")
