from celery import Celery, chain
from edapi import EdAPI
from edapi.models.user import User
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pinecone import Pinecone, Index
import itertools
from celery_worker import app

# Load environment variables
load_dotenv()

PINE_CONE_API_KEY = os.getenv("PINECONE_API_KEY")
DB_URI = os.getenv("MONGO_DB_URI")
# Initialize Celery

# Initialize connections
client = MongoClient(DB_URI)
db = client[os.getenv('DB_NAME', 'ed_summarizer')]

pc = Pinecone(api_key=PINE_CONE_API_KEY)
INDEX_NAME = "ed-summarizer-index"
if not pc.has_index(INDEX_NAME):
    pc.create_index_for_model(
        name=INDEX_NAME,
        cloud="aws",
        region="us-east-1",
        embed={
            "model": "llama-text-embed-v2",
            "field_map": {"text": "content"}
        }
    )


@app.task
def fetch_and_store_threads():
    """
    Get all users, fetch their threads from selected units and store in vector DB
    Keep track of the unit_id used as there can be duplicate amongs users
    """

    # Get all users
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
                    "content": thread_content
                })
        insert_to_vector_db(documents, namespace=str(unit_info["unit_id"]))
        processed_units.add(unit_id)

    db.task_records.insert_one({
        "unit_ids": list(processed_units),

    })
    return "All threads fetched and stored successfully"


def chunks(iterable, batch_size=200):
    """A helper function to break an iterable into chunks of size batch_size."""
    it = iter(iterable)
    chunk = list(itertools.islice(it, batch_size))
    while chunk:
        yield chunk
        chunk = list(itertools.islice(it, batch_size))


def insert_to_vector_db(documents: List[str], namespace: str, index_name: str = INDEX_NAME):
    """
    Insert documents into the vector database
    [{id:str, category:str, content: str }]
    """
    index = pc.Index(index_name)
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
