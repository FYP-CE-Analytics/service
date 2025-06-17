from enum import Enum
from typing import Dict

class TaskStatus(str, Enum):
    RECEIVED = "received"
    PENDING = "pending"
    RUNNING_FETCH_THREADS = "running fetch_and_store_threads_by_unit"
    RUNNING_FETCH_THREADS_CATEGORY = "running fetch_and_store_threads_by_unit_by_category"
    INSERTING_SUCCESS = "inserting success"
    RUNNING_CLUSTERING = "running clustering"
    FINISH_CLUSTERING = "finish clustering"
    RUNNING_AGENT_ANALYSIS = "running agent analysis"
    RUNNING_UNIT_TREND_ANALYSIS = "running unit trend analysis"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"

# Map task status to progress percentage
TASK_STATUS_PROGRESS: Dict[str, int] = {
    TaskStatus.RECEIVED: 0,
    TaskStatus.PENDING: 0,
    TaskStatus.RUNNING_FETCH_THREADS: 10,
    TaskStatus.RUNNING_FETCH_THREADS_CATEGORY: 10,
    TaskStatus.INSERTING_SUCCESS: 20,
    TaskStatus.RUNNING_CLUSTERING: 40,
    TaskStatus.FINISH_CLUSTERING: 60,
    TaskStatus.RUNNING_AGENT_ANALYSIS: 80,
    TaskStatus.RUNNING_UNIT_TREND_ANALYSIS: 80,
    TaskStatus.COMPLETED: 100,
    TaskStatus.SUCCESS: 100,
    TaskStatus.FAILURE: 0,
    TaskStatus.ERROR: 0
} 