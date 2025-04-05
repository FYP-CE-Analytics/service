from celery import Celery, chain
from edapi import EdAPI
from edapi.models.user import User
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pinecone import Pinecone, Index
import itertools


PINE_CONE_API_KEY = os.getenv("PINECONE_API_KEY")
# Initialize Celery
app = Celery('ed_summarizer',
             broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
             backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))

# Load environment variables
load_dotenv()

# Initialize connections
client = MongoClient(os.getenv('MONGODB_URI'))
db = client[os.getenv('DB_NAME', 'ed_summarizer')]

pc = Pinecone(api_key=PINE_CONE_API_KEY)
index_name = "ed_summarizer_index"
if not pc.has_index(index_name):
    pc.create_index_for_model(
        name=index_name,
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
    users = db.users.find({})
    for user in users:
        # Get user's selected units
        selected_units = user.get('selected_units', [])
        edApi_client = EdAPI(user['api_key'])

        for unit_id in selected_units:
            # Fetch threads for this unit
            threads = edApi_client.list_all_students_threads()
            # to do check if its already inserted

            # Process and store threads in vector DB
            documents = []

            for thread in threads:
                thread_content = f"Title: {thread.title}\nContent: {thread.content}"
                documents.append({
                    "id": thread.id,
                    "category": thread.category,
                    "content": thread_content
                })
        insert_to_vector_db(documents, namespace=unit_id)

    return "All threads fetched and stored successfully"


def chunks(iterable, batch_size=200):
    """A helper function to break an iterable into chunks of size batch_size."""
    it = iter(iterable)
    chunk = list(itertools.islice(it, batch_size))
    while chunk:
        yield chunk
        chunk = list(itertools.islice(it, batch_size))


def insert_to_vector_db(documents: List[str], namespace: str, index_name: str = index_name):
    """
    Insert documents into the vector database
    [{id:str, category:str, content: str }]
    """
    index = pc.Index(index_name)

    for batch in chunks(documents, batch_size=200):
        try:
            index.upsert(
                vectors=batch,
                namespace=namespace
            )

        except Exception as e:
            print(f"Error inserting batch into vector DB: {e}")
            continue
