from odmantic import Field, Model
from datetime import datetime
from typing import Dict, Any, Optional


class TaskTransactionModel(Model):
    """
    Store the task transaction
    """
    task_id: str = Field()
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)
    unit_id: str = Field(default="")
    error_message: str = Field(default="")
    input: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(default="")
    task_name: str = Field(default="")
