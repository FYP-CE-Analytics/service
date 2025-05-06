from celery import Celery, chain
from edapi import EdAPI
from edapi.models.user import User
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from app.services.pinecone_service import pc_service, INDEX_NAME
import itertools
from celery_worker import app
from app.schemas.tasks.storing_task_schema import StoringTaskResult
from datetime import datetime
from bson import ObjectId
from app.repositories.task_transaction_repository import TaskTransactionRepository
from app.utils.shared import parse_date
# Load environment variables
load_dotenv()

DB_URI = os.getenv("MONGO_DATABASE_URI")
# Initialize Celery

# Initialize connections
client = MongoClient(DB_URI)
db = client[os.getenv('DB_NAME', 'ed_summarizer')]

# to do allow for unit ids to be passed


@app.task
def fetch_and_store_threads(user_id: str = None) -> StoringTaskResult:
    """
    Get all users, fetch their threads from selected units and store in vector DB
    Keep track of the unit_id used as there can be duplicate amongs users
    filter out categories
    """
    users = []
    # if user_id is provided, fetch only that user
    if user_id:
        user = db.user.find_one({"_id": user_id})
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        users = [user]
    else:
        users = list(db.user.find({}))
    processed_units = set()
    for user in users:
        # Get user's selected units
        selected_units = user.get(
            'selected_units', [])  # dict

        ed_client = EdAPI(user['api_key'])
        for unit_info in selected_units:
            unit_id = unit_info["unit_id"]
            # Check if this unit has already been processed
            if unit_id in processed_units:
                continue
            # Fetch threads for this unit
            # to do check if threads already inserted
            threads = ed_client.list_all_students_threads(
                course_id=unit_info["unit_id"])
            # to do check if its already inserted

            # Process and store threads in vector DB
            documents = []
            for thread in threads:
                thread_content = f"Title: {thread.title}\nContent: {thread.document}"
                documents.append({
                    "id": str(thread.id),
                    "category": thread.category,
                    "content": thread_content,
                    "created_at": thread.created_at,
                })
        insert_to_vector_db(documents, namespace=str(unit_info["unit_id"]))
        processed_units.add(unit_id)

    db.task_records.insert_one({
        "unit_ids": list(processed_units),

    })
    return StoringTaskResult(
        status="success",
        message="Threads fetched and stored successfully",
        unit_ids=list(processed_units),
    )


@app.task
def fetch_and_store_threads_by_unit(user_id: str, unit_id: str, transaction_id: str, start_date=None, end_date=None) -> StoringTaskResult:
    """
    Fetch threads from a specific unit for a specific user and store in vector DB

    Args:
        user_id: ID of the user
        unit_id: ID of the unit to fetch threads from

    Returns:
        StoringTaskResult with status and message
    """

    print(f"Fetching threads for user {user_id} and unit {unit_id}...")
    # Find the user
    user = db.user.find_one({"_id": user_id})
    task_transaction_repo = TaskTransactionRepository()
    task_transaction_repo.update_task_status_sync(
        id=transaction_id,
        status="running fetch_and_store_threads_by_unit",

    )

    # If not found, try with ObjectId
    if not user:
        try:
            user = db.user.find_one({"_id": ObjectId(user_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {e}")
    print(f"User: {user}")
    # Check if the unit is in user's selected units
    selected_units = user.get('selected_units', [])
    print(f"Selected units: {selected_units}")
    unit_info = None
    for unit in selected_units:
        if unit["unit_id"] == unit_id:
            unit_info = unit
            break

    # if not unit_info:
    #     raise ValueError(
    #         f"Unit with id {unit_id} not found in user's selected units")

    # Initialize Ed API client
    ed_client = EdAPI(user['api_key'])

    # Fetch threads for this unit
    print(f"Fetching threads for unit {unit_id}...")
    threads = ed_client.list_all_students_threads(course_id=unit_id)
    if start_date and end_date:
        from datetime import datetime

        # Filter threads picing thread with updated_at between start_date and end_date
        print(
            f"Total threads fetched before filtering {start_date} to {end_date}: {len(threads)}")
        print(f"first few threads: {threads[:5]}")
        threads = [
            thread for thread in threads if parse_date(thread.created_at) and parse_date(start_date) <= parse_date(thread.created_at) <= parse_date(end_date)
        ]

    print(f"Fetched {len(threads)} threads")

    # Process and store threads in vector DB
    documents = []
    for thread in threads:
        thread_content = f"Title: {thread.title}\nContent: {thread.document}"
        documents.append({
            "id": str(thread.id),
            "category": thread.category,
            "content": thread_content,
            "created_at": str(thread.created_at),
        })

    # Insert into vector DB
    namespace = str(unit_id)
    insert_to_vector_db(documents, namespace=namespace)
    if len(documents) == 0:
        task_transaction_repo.update_task_status_sync(
            id=transaction_id,
            status="completed",
            error_message="No threads found to store",
            result={}
        )
        raise ValueError(
            f"No threads found for unit {unit_id} in the specified date range, please check the dates")

    # Record the task
    db.task_records.insert_one({
        "user_id": user_id,
        "unit_ids": [unit_id],
        "timestamp": datetime.now(),
        "thread_count": len(threads)
    })

    return StoringTaskResult(
        status="success",
        message=f"Fetched and stored {len(threads)} threads for unit {unit_id}",
        unit_ids=[unit_id],
        transaction_id=transaction_id

    ).model_dump()


def chunks(iterable, batch_size=200):
    """A helper function to break an iterable into chunks of size batch_size."""
    it = iter(iterable)
    chunk = list(itertools.islice(it, batch_size))
    while chunk:
        yield chunk
        chunk = list(itertools.islice(it, batch_size))


def insert_to_vector_db(documents: List[dict], namespace: str, index_name: str = INDEX_NAME):
    """
    Insert documents into the vector database
    [{id:str, category:str, content: str }]
    """
    index = pc_service.Index(index_name)
    print(index.describe_index_stats())
    print(f"Inserting {len(documents)} documents into vector DB...")
    print(f"Namespace: {namespace}")
    print(f"Index Name: {index_name}")

    for batch in chunks(documents, batch_size=50):
        print(f"Inserting batch of size {len(batch)}")
        try:
            index.upsert_records(
                records=batch,
                namespace=namespace,
            )

        except Exception as e:
            print(f"Error inserting batch into vector DB: {e}")

            continue


if __name__ == "__main__":
    # Run the task
    result = fetch_and_store_threads()
    print(result)
