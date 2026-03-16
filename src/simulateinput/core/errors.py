class SimulateInputError(Exception):
    """Base exception for the platform."""


class SessionNotFoundError(SimulateInputError):
    """Raised when a requested session does not exist."""


class CaseValidationError(SimulateInputError):
    """Raised when a case file is invalid."""


class DriverNotAvailableError(SimulateInputError):
    """Raised when a platform driver is unavailable."""
