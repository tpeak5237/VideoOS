class VideoOSError(Exception):
    """Base exception for expected VideoOS failures."""


class DependencyError(VideoOSError):
    """Raised when an optional or external dependency is unavailable."""


class ValidationError(VideoOSError):
    """Raised when user-provided values fail validation."""


class UnsafePathError(VideoOSError):
    """Raised when a path resolves outside its allowed project boundary."""


class ExternalCommandError(VideoOSError):
    """Raised when an external command fails."""
