import time
from celery import Celery, chain
from edapi import EdAPI
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
from app.utils.shared import parse_date, is_within_interval
from app.db.session import get_sync_client
from app.schemas.tasks.task_status import TaskStatus

# Load environment variables
load_dotenv()

db = get_sync_client()


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
        task_id=transaction_id,
        status=TaskStatus.RUNNING_FETCH_THREADS,
    )
    # If not found, try with ObjectId
    if not user:
        try:
            user = db.user.find_one({"_id": ObjectId(user_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {e}")

    # Initialize Ed API client
    ed_client = EdAPI(user['api_key'])

    # Fetch threads for this unit
    print(f"Fetching threads for unit {unit_id}...")
    threads = ed_client.list_all_students_threads(course_id=unit_id)
    if start_date or end_date:

        # Filter threads picing thread with between start_date and end_date
        print(
            f"Total threads fetched before filtering {start_date} to {end_date}: {len(threads)}")
        print(f"first few threads: {threads[:5]}")
        threads = [
            thread for thread in threads if is_within_interval(thread.created_at, start_date, end_date)
        ]

    print(f"Fetched {len(threads)} threads")

    # Process and store threads in vector DB
    #need to assign week number to each thread
    #get the week data from unit collection, return only the weeks field 
    unit_data = db.unit.find_one({"_id": int(unit_id)}, {"weeks": 1})
    # assign the weeks list from the document
    weeks = unit_data.get("weeks", [])
    documents = []
    for thread in threads:
        thread_content = f"Title: {thread.title}\nContent: {thread.document}"
        # find the week number from the weeks list
        week = next((week for week in weeks if is_within_interval(thread.created_at, week.get("start_date"), week.get("end_date"))), None)
        documents.append({
            "id": str(thread.id),
            "category": thread.subcategory if thread.subcategory else thread.category,
            "content": thread_content,
            "created_at": str(thread.created_at),
            "week_id": week['week_id'] if week else None,
            "week_number": week['teaching_week_number'] if week else None,
            "week_type": week['week_type'] if week else None
        })

    # Insert into vector DB
    namespace = str(unit_id)
    insert_to_vector_db(documents, namespace=namespace)
    if len(documents) == 0:
        task_transaction_repo.update_task_status_sync(
            task_id=transaction_id,
            status=TaskStatus.ERROR,
            error_message="No threads found to store",
            result={}
        )
        raise ValueError(
            f"No threads found for unit {unit_id} in the specified date range, please check the dates")

    task_result = StoringTaskResult(
        status="success",
        message=f"Fetched and stored {len(threads)} threads for unit {unit_id}",
        result={
            "unit_ids": [unit_id],
            "thread_ids": [thread.id for thread in threads],
        },
        transaction_id=transaction_id
    )

    task_transaction_repo.update_task_status_sync(
        task_id=transaction_id,
        status=TaskStatus.INSERTING_SUCCESS,
        result=task_result.model_dump()
    )
    print(f"Task result: {task_result.model_dump_json(indent=2)}")

    return task_result.model_dump()


@app.task
def fetch_and_store_threads_by_unit_by_category(user_id: str, unit_id: str, transaction_id: str, category: str = None) -> StoringTaskResult:
    """
    Fetch threads from a specific unit for a specific user and store in vector DB
    """
    print(f"Fetching threads for user {user_id} and unit {unit_id}...")
    # Find the user
    user = db.user.find_one({"_id": user_id})
    task_transaction_repo = TaskTransactionRepository()
    task_transaction_repo.update_task_status_sync(
        task_id=transaction_id,
        status=TaskStatus.RUNNING_FETCH_THREADS_CATEGORY,
    )
    # If not found, try with ObjectId
    if not user:
        try:
            user = db.user.find_one({"_id": ObjectId(user_id)})
        except Exception as e:
            print(f"Error converting to ObjectId: {e}")

    # Initialize Ed API client
    ed_client = EdAPI(user['api_key'])

    # Fetch threads for this unit  
    threads = ed_client.list_all_students_threads(course_id=unit_id)
    unit_data = db.unit.find_one({"_id": int(unit_id)}, {"weeks": 1})
    # assign the weeks list from the document
    weeks = unit_data.get("weeks", [])
    

    # Filter threads by category if provided
    if category:
        threads = [thread for thread in threads if thread.subcategory == category or thread.category == category]
        print(f"Total threads fetched before filtering by category {category}: {len(threads)}")
        print(f"first few threads: {threads[:5]}")


    # Process and store threads in vector DB
    documents = []
    for thread in threads:
        thread_content = f"Title: {thread.title}\nContent: {thread.document}"
        # find the week number from the weeks list
        week = next((week for week in weeks if is_within_interval(thread.created_at, week.get("start_date"), week.get("end_date"))), None)
        documents.append({
            "id": str(thread.id),
            "category": thread.subcategory if thread.subcategory else thread.category,
            "content": thread_content,
            "created_at": str(thread.created_at),
            "week_id": week['week_id'] if week else None,
            "week_number": week['teaching_week_number'] if week else None,
            "week_type": week['week_type'] if week else None
        })

    namespace = str(unit_id)
    insert_to_vector_db(documents, namespace=namespace)
    if len(documents) == 0:
        task_transaction_repo.update_task_status_sync(
            task_id=transaction_id,
            status=TaskStatus.ERROR,
            error_message="No threads found to store",
            result={}
        )
        raise ValueError(
            f"No threads found for unit {unit_id} in the specified date range, please check the dates")
    
    task_result = StoringTaskResult(
        status="success",
        message=f"Fetched and stored {len(threads)} threads for unit {unit_id}",
        result={
            "unit_ids": [unit_id],
            "thread_ids": [thread.id for thread in threads],
        },
        transaction_id=transaction_id
    )

    task_transaction_repo.update_task_status_sync(
        task_id=transaction_id,
        status=TaskStatus.INSERTING_SUCCESS,
        result=task_result.model_dump()
    )
    print(f"Task result: {task_result.model_dump_json(indent=2)}")

    return task_result.model_dump()

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
        ##batch is a list of thead dicts
        ##maybe need to chunk the content within the thread dict
        print(f"Inserting batch of size {len(batch)}")
        try:
            index.upsert_records(
                records=batch,
                namespace=namespace,
            )

        except Exception as e:
            print(f"Error inserting batch into vector DB: {e}")

            continue
    time.sleep(10)

if __name__ == "__main__":
    # Run the task
    result = fetch_and_store_threads()
    print(result)
