"""Application-level exceptions.

Every error that is safe to show to a user derives from :class:`CourseGenError`.
Unexpected errors are left untouched and reported by the UI boundary.
"""


class CourseGenError(Exception):
    """Base class for expected, user-facing errors."""


class ConfigurationError(CourseGenError):
    """A required setting or credential file is missing."""


class ValidationError(CourseGenError):
    """User input is invalid."""


class DuplicateUserError(ValidationError):
    """A unique user field (name or email) already exists."""


class AuthenticationError(CourseGenError):
    """Credentials are missing or incorrect."""


class DatabaseError(CourseGenError):
    """The database is unreachable or a query failed."""


class ExternalServiceError(CourseGenError):
    """A third-party service (CDN, Google Drive, SMTP) failed."""


class GenerationError(CourseGenError):
    """An AI or media generation step failed."""
