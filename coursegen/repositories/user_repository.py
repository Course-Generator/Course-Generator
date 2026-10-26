"""MongoDB repository for user accounts and their generated media."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from coursegen.errors import DatabaseError, DuplicateUserError
from coursegen.models import PendingRegistration, UserAccount
from coursegen.repositories.mongo import get_database

logger = logging.getLogger(__name__)

_DB_UNAVAILABLE = (
    "Could not reach the database. Make sure MongoDB is running and "
    "MONGODB_URI / MONGODB_DB are configured correctly."
)


class UserRepository:
    def __init__(self, database: Any | None = None) -> None:
        self._collection = (database or get_database())["users"]
        self._indexes_ready = False

    # ------------------------------------------------------------------ reads
    def find_by_id(self, user_id: str) -> Optional[UserAccount]:
        object_id = self._object_id(user_id)
        if object_id is None:
            return None
        document = self._safe(self._collection.find_one, {"_id": object_id})
        return self._to_account(document)

    def find_by_email(self, email: str) -> Optional[UserAccount]:
        document = self._safe(self._collection.find_one, {"email": email.strip()})
        return self._to_account(document)

    def find_by_name(self, name: str) -> Optional[UserAccount]:
        document = self._safe(self._collection.find_one, {"name": name.strip()})
        return self._to_account(document)

    def exists_email(self, email: str) -> bool:
        return self._safe(self._collection.find_one, {"email": email.strip()}, {"_id": 1}) is not None

    def exists_name(self, name: str) -> bool:
        return self._safe(self._collection.find_one, {"name": name.strip()}, {"_id": 1}) is not None

    # ----------------------------------------------------------------- writes
    def insert(self, pending: PendingRegistration) -> str:
        self._ensure_indexes()
        document = {
            "name": pending.name,
            "email": pending.email,
            "age": pending.age,
            "gender": pending.gender,
            "salt": pending.salt,
            "password": pending.password_hash,
        }
        try:
            result = self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise DuplicateUserError("Name or email is already registered.") from exc
        except PyMongoError as exc:
            raise DatabaseError(_DB_UNAVAILABLE) from exc
        return str(result.inserted_id)

    def update_profile(self, user_id: str, name: str, age: int, gender: str) -> bool:
        object_id = self._object_id(user_id)
        if object_id is None:
            return False
        try:
            result = self._collection.update_one(
                {"_id": object_id},
                {"$set": {"name": name, "age": age, "gender": gender}},
            )
        except DuplicateKeyError as exc:
            raise DuplicateUserError("Name is already used.") from exc
        except PyMongoError as exc:
            raise DatabaseError(_DB_UNAVAILABLE) from exc
        return result.modified_count == 1

    def update_password(self, user_id: str, password_hash: str, salt: str) -> bool:
        return self._update_fields(user_id, {"password": password_hash, "salt": salt})

    def update_email(self, user_id: str, email: str) -> bool:
        object_id = self._object_id(user_id)
        if object_id is None:
            return False
        try:
            result = self._collection.update_one(
                {"_id": object_id},
                {"$set": {"email": email}},
            )
        except DuplicateKeyError as exc:
            raise DuplicateUserError("Email is already used.") from exc
        except PyMongoError as exc:
            raise DatabaseError(_DB_UNAVAILABLE) from exc
        return result.modified_count == 1

    # ------------------------------------------------------------------ media
    def add_video(self, user_id: str, name: str, path: str) -> bool:
        return self._add_media(user_id, "videos", name, path)

    def add_presentation(self, user_id: str, name: str, path: str) -> bool:
        return self._add_media(user_id, "pptx", name, path)

    def delete_video(self, user_id: str, name: str) -> bool:
        return self._delete_media(user_id, "videos", name)

    def delete_presentation(self, user_id: str, name: str) -> bool:
        return self._delete_media(user_id, "pptx", name)

    def list_videos(self, user_id: str) -> Dict[str, str]:
        return self._list_media(user_id, "videos")

    def list_presentations(self, user_id: str) -> Dict[str, str]:
        return self._list_media(user_id, "pptx")

    # --------------------------------------------------------------- internal
    def _add_media(self, user_id: str, field: str, name: str, path: str) -> bool:
        object_id = self._object_id(user_id)
        if object_id is None:
            return False
        result = self._safe(
            self._collection.update_one,
            {"_id": object_id, f"{field}.name": {"$ne": name}},
            {"$push": {field: {"name": name, "path": path}}},
        )
        return result.modified_count == 1

    def _delete_media(self, user_id: str, field: str, name: str) -> bool:
        object_id = self._object_id(user_id)
        if object_id is None:
            return False
        result = self._safe(
            self._collection.update_one,
            {"_id": object_id},
            {"$pull": {field: {"name": name}}},
        )
        return result.modified_count == 1

    def _list_media(self, user_id: str, field: str) -> Dict[str, str]:
        object_id = self._object_id(user_id)
        if object_id is None:
            return {}
        document = self._safe(self._collection.find_one, {"_id": object_id}, {field: 1})
        if not document:
            return {}
        return {
            str(item.get("name")): str(item.get("path"))
            for item in document.get(field, [])
            if item.get("name") and item.get("path")
        }

    def _update_fields(self, user_id: str, fields: Dict[str, Any]) -> bool:
        object_id = self._object_id(user_id)
        if object_id is None:
            return False
        document = self._safe(
            self._collection.find_one_and_update,
            {"_id": object_id},
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )
        return document is not None

    def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        try:
            self._collection.create_index("email", unique=True, name="uniq_email")
            self._collection.create_index("name", unique=True, name="uniq_name")
        except PyMongoError as exc:
            logger.warning("Could not create user indexes: %s", exc)
        self._indexes_ready = True

    @staticmethod
    def _object_id(value: str) -> Optional[ObjectId]:
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            return None

    @staticmethod
    def _to_account(document: Optional[Dict[str, Any]]) -> Optional[UserAccount]:
        if not document:
            return None
        return UserAccount(
            id=str(document["_id"]),
            name=str(document.get("name", "")),
            email=str(document.get("email", "")),
            age=int(document.get("age", 0)),
            gender=str(document.get("gender", "")),
            password_hash=str(document.get("password", "")),
            salt=str(document.get("salt", "")),
        )

    @staticmethod
    def _safe(operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return operation(*args, **kwargs)
        except PyMongoError as exc:
            logger.error("Database operation failed: %s", exc)
            raise DatabaseError(_DB_UNAVAILABLE) from exc
