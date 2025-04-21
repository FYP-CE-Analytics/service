from dotenv import load_dotenv
import os
load_dotenv()


class Settings():
    API_V1_STR: str = "/api/v1"
    # MongoDB settings
    MONGO_DATABASE_URI: str = os.getenv(
        "MONGO_DATABASE_URI", "mongodb://admin:secret@localhost:27017")
    MONGO_DATABASE_NAME: str = os.getenv("DB_NAME", "ed_summarizer")


settings = Settings()
