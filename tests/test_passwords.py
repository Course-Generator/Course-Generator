"""Unit tests for password hashing and legacy compatibility."""

from __future__ import annotations

import hashlib
import unittest

from coursegen.security.passwords import PasswordHasher


class PasswordHasherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hasher = PasswordHasher()

    def test_new_hash_round_trip(self) -> None:
        stored, salt = self.hasher.hash_password("correct horse battery")
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        self.assertTrue(salt)
        self.assertTrue(self.hasher.verify("correct horse battery", salt, stored))
        self.assertFalse(self.hasher.verify("wrong password", salt, stored))

    def test_salts_are_unique(self) -> None:
        first, first_salt = self.hasher.hash_password("same password")
        second, second_salt = self.hasher.hash_password("same password")
        self.assertNotEqual(first_salt, second_salt)
        self.assertNotEqual(first, second)

    def test_legacy_sha256_is_accepted(self) -> None:
        salt = "a1b2c3"
        legacy = hashlib.sha256((salt + "old-secret").encode("utf-8")).hexdigest()
        self.assertTrue(self.hasher.verify("old-secret", salt, legacy))
        self.assertFalse(self.hasher.verify("new-secret", salt, legacy))

    def test_needs_rehash(self) -> None:
        legacy = hashlib.sha256(b"anything").hexdigest()
        self.assertTrue(self.hasher.needs_rehash(legacy))

        current, _ = self.hasher.hash_password("current")
        self.assertFalse(self.hasher.needs_rehash(current))

        weak = f"pbkdf2_sha256$1000$salt${'0' * 64}"
        self.assertTrue(self.hasher.needs_rehash(weak))

    def test_malformed_hash_is_rejected(self) -> None:
        self.assertFalse(self.hasher.verify("password", "salt", "pbkdf2_sha256$broken"))
        self.assertFalse(self.hasher.verify("password", "salt", ""))


if __name__ == "__main__":
    unittest.main()
