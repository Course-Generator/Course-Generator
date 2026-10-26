"""Unit tests for input validators and filename handling."""

from __future__ import annotations

import unittest

from coursegen.security.validators import EmailValidator, NameValidator, PasswordValidator
from coursegen.utils import safe_filename


class EmailValidatorTests(unittest.TestCase):
    def test_valid_emails(self) -> None:
        for email in ("student@example.com", "a_b@sub.domain.org", "  user@mail.co  "):
            self.assertTrue(EmailValidator.is_valid(email), email)

    def test_invalid_emails(self) -> None:
        for email in ("", "student@", "student.example.com", "a b@example.com", "@example.com"):
            self.assertFalse(EmailValidator.is_valid(email), email)


class NameValidatorTests(unittest.TestCase):
    def test_valid_names(self) -> None:
        for name in ("Ahmed", "Sara2", "محمد"):
            self.assertTrue(NameValidator.is_valid(name), name)

    def test_special_characters_and_spaces(self) -> None:
        for name in ("Ah med", "Ah-med", "O'Neil", "user@name", ""):
            self.assertFalse(NameValidator.is_valid(name), name)


class PasswordValidatorTests(unittest.TestCase):
    def test_length_and_confirmation(self) -> None:
        self.assertFalse(PasswordValidator.is_valid("short"))
        self.assertTrue(PasswordValidator.is_valid("long-enough"))
        self.assertTrue(PasswordValidator.matches("abc", "abc"))
        self.assertFalse(PasswordValidator.matches("abc", "abd"))


class FilenameTests(unittest.TestCase):
    def test_unsafe_characters_are_replaced(self) -> None:
        self.assertEqual(safe_filename("My:Course/One?"), "My_Course_One_")
        self.assertEqual(safe_filename("   "), "file")
        self.assertEqual(safe_filename("", "course"), "course")


if __name__ == "__main__":
    unittest.main()
