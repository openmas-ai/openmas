"""Exceptions for OpenMAS."""

from typing import Any, Dict, Optional


class OpenMasError(Exception):
    """Base exception for all OpenMAS errors."""


class ConfigurationError(OpenMasError):
    """Error raised when there is a configuration problem."""


class DependencyError(OpenMasError):
    """Error raised when a required optional dependency is not installed."""

    def __init__(self, message: str, dependency: str, extras: Optional[str] = None) -> None:
        """Initialize a DependencyError.

        Args:
            message: Error message
            dependency: The name of the missing dependency
            extras: The extras group that can be installed to get this dependency
        """
        self.dependency = dependency
        self.extras = extras
        super().__init__(message)


class CommunicationError(OpenMasError):
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


class ValidationError(OpenMasError):
    """Error raised when validation fails."""


class LifecycleError(OpenMasError):
    """Error raised when there is a problem with the agent lifecycle."""
