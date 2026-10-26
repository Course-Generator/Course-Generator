"""MongoDB connection management."""

from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from coursegen.config import get_settings


@lru_cache(maxsize=1)
def get_database() -> Database:
    settings = get_settings()
    client = MongoClient(
        settings.mongo_uri,
        serverSelectionTimeoutMS=3_000,
        connect=False,
    )
    return client[settings.mongo_db]
