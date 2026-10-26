"""Pure input validators (no database or framework dependencies)."""

from __future__ import annotations

import re

PASSWORD_MIN_LENGTH = 8


class EmailValidator:
    _PATTERN = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

    @classmethod
    def is_valid(cls, email: str) -> bool:
        return bool(email and cls._PATTERN.match(email.strip()))


class NameValidator:
    _SPECIAL_CHARACTERS = re.compile(r"[!@#$%^&*()_+\-=\[\]{};'\\|,.<>\/?\s]+")

    @classmethod
    def has_special_characters(cls, name: str) -> bool:
        return bool(name and cls._SPECIAL_CHARACTERS.search(name))

    @classmethod
    def is_valid(cls, name: str) -> bool:
        return bool(name and not cls.has_special_characters(name))


class PasswordValidator:
    @staticmethod
    def is_valid(password: str) -> bool:
        return len(password or "") >= PASSWORD_MIN_LENGTH

    @staticmethod
    def matches(password: str, confirmation: str) -> bool:
        return password == confirmation
