from odmantic import Field, Model
from datetime import datetime
from typing import Dict, Any, Optional
from app.schemas.tasks.task_status import TaskStatus


class TaskTransactionModel(Model):
    """
    Store the task transaction
    """
    task_id: Optional[str] = Field()
    celery_task_id: Optional[str] = Field(default=None)
    status: TaskStatus = Field(default=TaskStatus.RECEIVED)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)
    unit_id: str = Field(default="")
    error_message: str = Field(default="")
    input: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = Field(default_factory=dict)
    user_id: str = Field(default="")
    task_name: str = Field(default="")
    progress: int = Field(default=0)
