"""Custom exceptions for the asset management module."""

from typing import Optional


class AssetError(Exception):
    """Base class for all asset-related exceptions."""

    pass


class AssetConfigurationError(AssetError):
    """Exception raised when there is an issue with asset configuration."""

    pass


class AssetDownloadError(AssetError):
    """Exception raised when there is an error downloading an asset."""

    def __init__(self, message: str, source_type: Optional[str] = None, source_info: Optional[str] = None):
        """Initialize the exception.

        Args:
            message: The error message
            source_type: The type of source (http, hf, local)
            source_info: Additional information about the source
        """
        self.source_type = source_type
        self.source_info = source_info
        super().__init__(message)


class AssetAuthenticationError(AssetDownloadError):
    """Exception raised when there is an authentication error downloading an asset."""

    def __init__(
        self,
        message: str,
        source_type: Optional[str] = None,
        source_info: Optional[str] = None,
        token_env_var: Optional[str] = None,
    ):
        """Initialize the exception.

        Args:
            message: The error message
            source_type: The type of source (http, hf, local)
            source_info: Additional information about the source
            token_env_var: The environment variable that was expected to contain the token
        """
        self.token_env_var = token_env_var
        super().__init__(message, source_type, source_info)


class AssetVerificationError(AssetError):
    """Exception raised when there is an error verifying an asset."""

    pass


class AssetUnpackError(AssetError):
    """Exception raised when there is an error unpacking an asset."""

    pass
