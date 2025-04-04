from dotenv import load_dotenv
import os
load_dotenv()


class Settings():
    API_V1_STR: str = "/api/v1"
    # MongoDB settings
    MONGO_DATABASE_URI: str = os.getenv(
        "MONGO_DATABASE_URI", "mongodb://admin:secret@localhost:27017")
    MONGO_DATABASE: str = "mydatabase"


settings = Settings()
