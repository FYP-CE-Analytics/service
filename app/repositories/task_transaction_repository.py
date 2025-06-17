from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.db.session import MongoDatabase, get_engine
from app.models.task_transaction import TaskTransactionModel
from app.schemas.tasks.task_status import TaskStatus, TASK_STATUS_PROGRESS


class TaskTransactionRepository:
    """Repository for managing task transactions using the singleton MongoDB connection"""

    def __init__(self):
        """Initialize using the singleton database connection"""
        self.db = MongoDatabase()
        self.engine = get_engine()
        self.collection_name = "task_transaction"

    async def create_task(self, task_name: str, unit_id: str, user_id: str, input: dict) -> TaskTransactionModel:
        """Create a new task transaction"""
        task = TaskTransactionModel(
            task_id="",
            status=TaskStatus.RECEIVED,
            created_at=datetime.now(),
            unit_id=unit_id,
            user_id=user_id,
            task_name=task_name,
            input=input,
            progress=0
        )
        print(f"Creating task: {task}")
        return await self.engine.save(task)

    async def get_transaction_by_id(self, trans_id: str) -> Optional[TaskTransactionModel]:
        """Get task by its Celery task ID"""
        return await self.engine.find_one(TaskTransactionModel,  TaskTransactionModel.id == ObjectId(trans_id))

    async def get_tasks_by_unit_id(self, unit_id: str) -> List[TaskTransactionModel]:
        """Get all tasks for a unit"""
        return await self.engine.find(TaskTransactionModel, TaskTransactionModel.unit_id == unit_id)

    async def get_tasks_by_user_id(self, user_id: str) -> List[TaskTransactionModel]:
        """Get all tasks for a user"""
        return await self.engine.find(TaskTransactionModel, TaskTransactionModel.user_id == user_id)

    # Sync methods for non-async contexts (like Celery tasks)
    def create_task_sync(self, task_id: str, task_name: str, unit_id: str = "", user_id: str = "", input="") -> Dict:
        """Create a new task transaction synchronously"""
        task = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now(),
            "unit_id": unit_id,
            "user_id": user_id,
            "task_name": task_name,
            "error_message": "",
            "result": {},
            "progress": 0
        }

        result = self.db[self.collection_name].insert_one(task)
        task["_id"] = result.inserted_id
        return task

    def update_task_status_sync(self, task_id: str, status: TaskStatus,
                                error_message: str = "",
                                result: Dict[str, Any] = None,
                                celery_task_id: str = None) -> Optional[Dict]:
        """Update task status and optional fields synchronously"""
        try:
            # Make sure we're using the right database access method
            # Direct access to the MongoDB collection
            from pymongo import MongoClient
            import os

            # Get a direct connection to MongoDB
            client = MongoClient(os.getenv("MONGO_DATABASE_URI"))
            db = client[os.getenv('DB_NAME', 'ed_summarizer')]

            # Find the document
            transaction = db[self.collection_name].find_one(
                {"_id": ObjectId(task_id)})
            if not transaction:
                print(f"Transaction with id {task_id} not found")
                return None

            # Get progress from status
            progress = TASK_STATUS_PROGRESS.get(status, 0)

            # Prepare update data
            update_data = {
                "status": status,
                "progress": progress
            }
            if status in [TaskStatus.COMPLETED, TaskStatus.SUCCESS]:
                update_data["completed_at"] = datetime.now()
            if error_message:
                update_data["error_message"] = error_message
            if result:
                update_data["result"] = result
            if celery_task_id:
                update_data["celery_task_id"] = celery_task_id

            # Use update_one with $set operator instead of replace_one
            db[self.collection_name].update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_data}
            )

            # Return the updated document
            updated_transaction = db[self.collection_name].find_one(
                {"_id": ObjectId(task_id)})
            return updated_transaction

        except Exception as e:
            print(f"Error updating task status: {str(e)}")
            return None
        
    async def get_task_result_by_unit_id_and_name(self, unit_id: str, name: str) -> Optional[List[TaskTransactionModel]]:
        """Get task result by unit id and name"""
        print(f"Getting task result by unit id and name: {unit_id}, {name}")
        return await self.engine.find(TaskTransactionModel, TaskTransactionModel.unit_id == unit_id, TaskTransactionModel.task_name == name)
