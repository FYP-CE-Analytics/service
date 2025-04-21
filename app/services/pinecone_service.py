from pinecone import Pinecone
import os
from dotenv import load_dotenv

PINE_CONE_API_KEY = os.getenv("PINECONE_API_KEY")
pc_service = Pinecone(api_key=PINE_CONE_API_KEY)

INDEX_NAME = "ed-summarizer-index"
if not pc_service.has_index(INDEX_NAME):
    pc_service.create_index_for_model(
        name=INDEX_NAME,
        cloud="aws",
        region="us-east-1",
        embed={
            "model": "llama-text-embed-v2",
            "field_map": {"text": "content"}
        }
    )
