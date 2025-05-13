from pydantic import BaseModel, Field
from app.schemas.tasks.base_task_result_schema import TaskResult


class StoringTaskIds(BaseModel):
    """
    Schema for the result of a storing task.
    """
    unit_ids: list[str] = Field(...,
                                description="List of unit IDs processed in the task")
    thread_ids: list[int] = Field(...,
                                description="List of thread IDs processed in the task")


StoringTaskResult = TaskResult[StoringTaskIds]
