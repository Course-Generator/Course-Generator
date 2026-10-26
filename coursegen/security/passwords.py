"""Password hashing with PBKDF2-SHA256 and legacy hash support."""

from __future__ import annotations

import hashlib
import hmac
import secrets


class PasswordHasher:
    """Hash passwords and verify both new and legacy stored hashes.

    New hashes use ``pbkdf2_sha256$<iterations>$<salt>$<digest>``.
    Legacy hashes (plain SHA-256 of ``salt + password``) are still accepted
    so existing accounts can log in and are upgraded transparently.
    """

    ALGORITHM = "pbkdf2_sha256"
    ITERATIONS = 260_000
    SALT_BYTES = 16

    def hash_password(self, password: str) -> tuple[str, str]:
        salt = secrets.token_hex(self.SALT_BYTES)
        digest = self._derive(password, salt, self.ITERATIONS)
        return f"{self.ALGORITHM}${self.ITERATIONS}${salt}${digest}", salt

    def verify(self, password: str, salt: str, stored_hash: str) -> bool:
        if not stored_hash:
            return False
        if stored_hash.startswith(f"{self.ALGORITHM}$"):
            try:
                _, iterations, stored_salt, digest = stored_hash.split("$", 3)
                candidate = self._derive(password, stored_salt, int(iterations))
            except (ValueError, TypeError):
                return False
            return hmac.compare_digest(candidate, digest)

        legacy_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy_hash, stored_hash)

    def needs_rehash(self, stored_hash: str) -> bool:
        if not stored_hash.startswith(f"{self.ALGORITHM}$"):
            return True
        try:
            return int(stored_hash.split("$", 3)[1]) < self.ITERATIONS
        except (IndexError, ValueError):
            return True

    @staticmethod
    def _derive(password: str, salt: str, iterations: int) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
