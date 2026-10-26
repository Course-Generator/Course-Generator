"""Authentication, registration, and profile operations."""

from __future__ import annotations

import hmac
import logging
from functools import lru_cache
from typing import Optional, Tuple

from coursegen.errors import AuthenticationError, DuplicateUserError, ValidationError
from coursegen.infrastructure.email_sender import EmailSender
from coursegen.models import PendingRegistration, UserAccount
from coursegen.repositories.user_repository import UserRepository
from coursegen.security.passwords import PasswordHasher
from coursegen.security.validators import (
    PASSWORD_MIN_LENGTH,
    EmailValidator,
    NameValidator,
    PasswordValidator,
)

logger = logging.getLogger(__name__)

_GENDERS = {"Male", "Female", "Other"}


class AuthService:
    def __init__(
        self,
        users: UserRepository | None = None,
        email_sender: EmailSender | None = None,
        hasher: PasswordHasher | None = None,
    ) -> None:
        self._users = users or UserRepository()
        self._email = email_sender or EmailSender()
        self._hasher = hasher or PasswordHasher()

    # ------------------------------------------------------------- registration
    def register(
        self,
        name: str,
        email: str,
        age: int,
        gender: str,
        password: str,
        confirmation: str,
    ) -> Tuple[PendingRegistration, str]:
        name = name.strip()
        email = email.strip()
        self._validate_registration(name, email, age, gender, password, confirmation)

        password_hash, salt = self._hasher.hash_password(password)
        pending = PendingRegistration(
            name=name,
            email=email,
            age=age,
            gender=gender,
            password_hash=password_hash,
            salt=salt,
        )
        code = self._email.send_verification_code(email)
        return pending, code

    def complete_registration(
        self,
        pending: Optional[PendingRegistration],
        submitted_code: str,
        expected_code: str,
    ) -> UserAccount:
        if pending is None:
            raise ValidationError("Your registration session expired. Please register again.")
        self.verify_code(submitted_code, expected_code)

        if self._users.exists_email(pending.email):
            raise DuplicateUserError("Email is already used.")
        if self._users.exists_name(pending.name):
            raise DuplicateUserError("Name is already used.")

        user_id = self._users.insert(pending)
        return UserAccount(
            id=user_id,
            name=pending.name,
            email=pending.email,
            age=pending.age,
            gender=pending.gender,
            password_hash=pending.password_hash,
            salt=pending.salt,
        )

    # --------------------------------------------------------------------- login
    def login(self, identifier: str, password: str) -> UserAccount:
        identifier = identifier.strip()
        if not identifier:
            raise ValidationError("Enter your email or name.")

        if EmailValidator.is_valid(identifier):
            account = self._users.find_by_email(identifier)
        else:
            account = self._users.find_by_name(identifier)

        if account is None:
            raise AuthenticationError("User not found.")
        if not self.verify_password(account, password):
            raise AuthenticationError("Password not correct.")

        if self._hasher.needs_rehash(account.password_hash):
            password_hash, salt = self._hasher.hash_password(password)
            self._users.update_password(account.id, password_hash, salt)
            account.password_hash = password_hash
            account.salt = salt
        return account

    def verify_password(self, account: UserAccount, password: str) -> bool:
        return self._hasher.verify(password, account.salt, account.password_hash)

    # ------------------------------------------------------------------- profile
    def update_profile(self, account: UserAccount, name: str, age: int, gender: str) -> UserAccount:
        name = name.strip()
        if not name:
            raise ValidationError("Name cannot be empty.")
        if not NameValidator.is_valid(name):
            raise ValidationError("Name must not contain spaces or special characters.")
        if age < 15 or age > 100:
            raise ValidationError("Age must be between 15 and 100.")
        if gender not in _GENDERS:
            raise ValidationError("Select a valid gender.")

        if name != account.name and self._users.exists_name(name):
            raise DuplicateUserError("Name is already used.")

        self._users.update_profile(account.id, name, age, gender)
        account.name = name
        account.age = age
        account.gender = gender
        return account

    def change_password(self, account: UserAccount, password: str, confirmation: str) -> UserAccount:
        self._validate_password(password, confirmation)
        if self.verify_password(account, password):
            raise ValidationError("This is the current password.")

        password_hash, salt = self._hasher.hash_password(password)
        self._users.update_password(account.id, password_hash, salt)
        account.password_hash = password_hash
        account.salt = salt
        return account

    # -------------------------------------------------------------- password reset
    def request_password_reset(self, email: str) -> str:
        email = email.strip()
        if not self._users.exists_email(email):
            raise ValidationError("Please enter a registered email address.")
        return self._email.send_verification_code(email)

    def reset_password(self, email: str, password: str, confirmation: str) -> None:
        self._validate_password(password, confirmation)
        account = self._users.find_by_email(email.strip())
        if account is None:
            raise ValidationError("Please enter a registered email address.")
        password_hash, salt = self._hasher.hash_password(password)
        self._users.update_password(account.id, password_hash, salt)

    # ------------------------------------------------------------------ email change
    def request_email_change(self, account: UserAccount, new_email: str) -> str:
        new_email = new_email.strip()
        if not EmailValidator.is_valid(new_email):
            raise ValidationError("Email is not in a valid format.")
        if new_email.lower() == account.email.lower():
            raise ValidationError("The new email must be different from the current one.")
        if self._users.exists_email(new_email):
            raise DuplicateUserError("Email is already used.")
        return self._email.send_verification_code(new_email)

    def confirm_email_change(
        self,
        account: UserAccount,
        new_email: str,
        submitted_code: str,
        expected_code: str,
    ) -> UserAccount:
        self.verify_code(submitted_code, expected_code)
        if self._users.exists_email(new_email):
            raise DuplicateUserError("Email is already used.")
        self._users.update_email(account.id, new_email)
        account.email = new_email
        return account

    # ------------------------------------------------------------------- helpers
    def _validate_registration(
        self,
        name: str,
        email: str,
        age: int,
        gender: str,
        password: str,
        confirmation: str,
    ) -> None:
        if not name:
            raise ValidationError("Name cannot be empty.")
        if not NameValidator.is_valid(name):
            raise ValidationError("Name must not contain spaces or special characters.")
        if self._users.exists_name(name):
            raise DuplicateUserError("Name is already used.")
        if not EmailValidator.is_valid(email):
            raise ValidationError("Email is not in a valid format.")
        if self._users.exists_email(email):
            raise DuplicateUserError("Email is already used.")
        if age < 15 or age > 100:
            raise ValidationError("Age must be between 15 and 100.")
        if gender not in _GENDERS:
            raise ValidationError("Select a valid gender.")
        self._validate_password(password, confirmation)

    @staticmethod
    def _validate_password(password: str, confirmation: str) -> None:
        if not PasswordValidator.is_valid(password):
            raise ValidationError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
            )
        if not PasswordValidator.matches(password, confirmation):
            raise ValidationError("Password and confirmation do not match.")

    @staticmethod
    def verify_code(submitted_code: str, expected_code: str) -> None:
        if not submitted_code or not expected_code or not hmac.compare_digest(
            str(submitted_code), str(expected_code)
        ):
            raise ValidationError("Incorrect verification code. Please try again.")


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService()
