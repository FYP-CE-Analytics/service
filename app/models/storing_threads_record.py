from odmantic import Field, Model
from datetime import datetime


class StoringRunRecordModel(Model):
    """
    Store the threads in vector DB
    """
    unit_ids: list[int] = Field(default_factory=list)
    run_time: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="pending")

    model_config = {
        "collection": "task_records",
    }
