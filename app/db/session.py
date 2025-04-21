from app.__version__ import __version__
from app.core.config import settings
from motor import motor_asyncio, core
from odmantic import AIOEngine
from pymongo.driver_info import DriverInfo
from app.models import UserModel, StoringRunRecordModel, ClusterResultModel

DRIVER_INFO = DriverInfo(
    name="full-stack-fastapi-mongodb", version=__version__)


class _MongoClientSingleton:
    mongo_client: motor_asyncio.AsyncIOMotorClient | None
    engine: AIOEngine

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(_MongoClientSingleton, cls).__new__(cls)
            cls.instance.mongo_client = motor_asyncio.AsyncIOMotorClient(
                settings.MONGO_DATABASE_URI, driver=DRIVER_INFO
            )
            cls.instance.engine = AIOEngine(
                client=cls.instance.mongo_client, database=settings.MONGO_DATABASE_NAME)
        return cls.instance


def MongoDatabase() -> core.AgnosticDatabase:
    return _MongoClientSingleton().mongo_client[settings.MONGO_DATABASE_NAME]


def get_engine() -> AIOEngine:
    return _MongoClientSingleton().engine


async def ping():
    await MongoDatabase().command("ping")


async def init_indexes():
    engine = get_engine()
    await engine.configure_database([UserModel, StoringRunRecordModel, ClusterResultModel])
    print("Indexes created successfully.")


__all__ = ["MongoDatabase", "ping"]
