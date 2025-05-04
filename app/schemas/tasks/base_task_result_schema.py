from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, TypeVar, Generic
from datetime import datetime

# Define a generic type variable
T = TypeVar('T')


class TaskResult(BaseModel, Generic[T]):
    """
    Generic schema for task results with consistent status pattern
    T represents the specific result data for each task type
    """
    status: str = Field(...,
                        description="Task status: success, error, warning")
    message: Optional[str] = Field(
        None, description="Optional message (required if error)")
    result: Optional[T] = Field(None, description="Task-specific result data")
    transaction_id: Optional[str] = Field(
        None, description="Transaction ID for tracking the task")
