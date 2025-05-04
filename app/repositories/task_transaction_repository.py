from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.db.session import MongoDatabase, get_engine
from app.models.task_transaction import TaskTransactionModel


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
            status="recieved",
            created_at=datetime.now(),
            unit_id=unit_id,
            user_id=user_id,
            task_name=task_name,
            input=input,
        )
        return await self.engine.save(task)

    async def update_task_status(self, id: str, status: str,
                                 error_message: str = "",
                                 result: Dict[str, Any] = None) -> Optional[TaskTransactionModel]:
        """Update task status and optional fields"""
        task = await self.engine.find_one(TaskTransactionModel, TaskTransactionModel.id == id)
        if not task:
            return None

        task.status = status
        if status in ["completed", "success"]:
            task.completed_at = datetime.now()
        if error_message:
            task.error_message = error_message
        if result:
            task.result = result

        return await self.engine.save(task)

    async def get_task_by_id(self, task_id: str) -> Optional[TaskTransactionModel]:
        """Get task by its Celery task ID"""
        return await self.engine.find_one(TaskTransactionModel, TaskTransactionModel.task_id == task_id)

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
            "status": "pending",
            "created_at": datetime.now(),
            "unit_id": unit_id,
            "user_id": user_id,
            "task_name": task_name,
            "error_message": "",
            "result": {}
        }

        result = self.db[self.collection_name].insert_one(task)
        task["_id"] = result.inserted_id
        return task

    def update_task_status_sync(self, id: str, status: str,
                                error_message: str = "",
                                result: Dict[str, Any] = None) -> Optional[Dict]:
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
                {"_id": ObjectId(id)})
            if not transaction:
                print(f"Transaction with id {id} not found")
                return None

            # Prepare update data
            update_data = {"status": status}
            if status in ["completed", "success"]:
                update_data["completed_at"] = datetime.now()
            if error_message:
                update_data["error_message"] = error_message
            if result:
                update_data["result"] = result

            # Use update_one with $set operator instead of replace_one
            db[self.collection_name].update_one(
                {"_id": ObjectId(id)},
                {"$set": update_data}
            )

            # Return the updated document
            updated_transaction = db[self.collection_name].find_one(
                {"_id": ObjectId(id)})
            return updated_transaction

        except Exception as e:
            print(f"Error updating task status: {str(e)}")
            return None
