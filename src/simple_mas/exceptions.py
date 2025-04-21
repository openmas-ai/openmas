"""Exceptions for SimpleMAS."""

from typing import Any, Dict, Optional


class SimpleMasError(Exception):
    """Base exception for all SimpleMAS errors."""


class ConfigurationError(SimpleMasError):
    """Error raised when there is a configuration problem."""


class CommunicationError(SimpleMasError):
    """Error raised when there is a communication problem."""

    def __init__(self, message: str, target: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize a CommunicationError.

        Args:
            message: Error message
            target: Target service name (if applicable)
            details: Additional error details
        """
        self.target = target
        self.details = details or {}
        super().__init__(message)


class ServiceNotFoundError(CommunicationError):
    """Error raised when a service is not found."""


class MethodNotFoundError(CommunicationError):
    """Error raised when a method is not found on a service."""


class RequestTimeoutError(CommunicationError):
    """Error raised when a request times out."""


class ValidationError(SimpleMasError):
    """Error raised when validation fails."""


class LifecycleError(SimpleMasError):
    """Error raised when there is a problem with the agent lifecycle."""
