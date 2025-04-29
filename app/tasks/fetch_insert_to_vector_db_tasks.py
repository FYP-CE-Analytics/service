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

# Load environment variables
load_dotenv()

DB_URI = os.getenv("MONGO_DB_URI")
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
                    "updated_at": thread.updated_at,
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
    print(f"Inserting {len(documents)} documents into vector DB...")
    print(f"Namespace: {namespace}")
    print(f"Index Name: {index_name}")

    for batch in chunks(documents, batch_size=200):
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
