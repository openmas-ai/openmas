"""Asset management configuration models for OpenMAS."""

from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class AssetAuthStrategy(str, Enum):
    """Defines the authentication strategy for an asset."""

    ENV_TOKEN = "env_token"  # Token is read from a specified environment variable
    # Future strategies could be added here, e.g., vault, explicit_value (not recommended for secrets)


class HttpAuthDetails(BaseModel):
    """Authentication details for assets downloaded over HTTP/S."""

    token_env_var: str = Field(description="Environment variable holding the authentication token.")
    scheme: str = Field(
        default="Bearer",
        description="Authentication scheme (e.g., Bearer, Token, Basic). "
        "Use an empty string if no scheme prefix is needed.",
    )
    header_name: str = Field(
        default="Authorization",
        description="The HTTP header to which the token will be added (e.g., Authorization, X-API-Key).",
    )


class HuggingFaceAuthDetails(BaseModel):
    """Authentication details for assets from Hugging Face Hub."""

    token_env_var: str = Field(
        default="HUGGINGFACE_TOKEN",
        description="Environment variable holding the Hugging Face Hub token. Defaults to HUGGINGFACE_TOKEN.",
    )


class AssetAuthentication(BaseModel):
    """Container for authentication details for an asset."""

    strategy: AssetAuthStrategy = AssetAuthStrategy.ENV_TOKEN
    http: Optional[HttpAuthDetails] = Field(None, description="Authentication details if source is 'http' or 'https'.")
    hf: Optional[HuggingFaceAuthDetails] = Field(None, description="Authentication details if source is 'hf'.")
    # Add other source types like 'gcp', 'aws_s3' here as needed

    @model_validator(mode="after")
    def validate_auth_details(self) -> "AssetAuthentication":
        """Validate that the appropriate authentication details are provided based on the strategy."""
        if self.strategy == AssetAuthStrategy.ENV_TOKEN:
            # For now we don't enforce specific validation rules, but this could be extended in the future
            pass
        return self


class AssetSourceConfig(BaseModel):
    """Configuration for an asset source."""

    type: Literal["http", "hf", "local"]
    url: Optional[str] = None
    repo_id: Optional[str] = None
    filename: Optional[str] = None
    revision: Optional[str] = None
    path: Optional[Path] = None
    authentication: Optional[AssetAuthentication] = Field(
        None, description="Authentication details required to download this asset."
    )
    progress_report: bool = Field(default=True, description="Enable progress reporting for this asset during download.")
    progress_report_interval_mb: float = Field(
        default=10.0, gt=0, description="Report progress approximately every X MB downloaded."
    )

    @model_validator(mode="after")
    def validate_source_fields(self) -> "AssetSourceConfig":
        """Validate that required fields are present based on source type."""
        # Check required fields based on source type
        if self.type == "http" and not self.url:
            raise ValueError("URL is required for HTTP source type")
        elif self.type == "hf" and not self.repo_id:
            raise ValueError("repo_id is required for Hugging Face source type")
        elif self.type == "local" and not self.path:
            raise ValueError("path is required for local source type")

        # Validate authentication details match the source type
        if self.authentication:
            if self.type == "http" and self.authentication.http is None:
                raise ValueError(
                    "HTTP authentication details must be provided when authentication is specified for HTTP source"
                )
            elif self.type == "hf" and self.authentication.hf is None:
                raise ValueError(
                    "Hugging Face authentication details must be provided "
                    "when authentication is specified for HF source"
                )
            elif self.type == "local" and self.authentication is not None:
                raise ValueError("Authentication is not applicable for local source type")
        return self


class AssetConfig(BaseModel):
    """Configuration for an asset."""

    name: str
    version: Optional[str] = "latest"
    asset_type: Optional[str] = "model"
    source: AssetSourceConfig
    checksum: Optional[str] = None
    unpack: Optional[bool] = False
    unpack_format: Optional[Literal["zip", "tar", "tar.gz", "tar.bz2"]] = None
    unpack_destination_is_file: bool = Field(
        default=False,
        description="If true and unpack is set, the unpacked content is expected to be a single file, "
        "and the path returned will be to this file directly within the asset's named directory.",
    )
    description: Optional[str] = None
    retries: int = Field(default=0, ge=0, description="Number of times to retry download on failure.")
    retry_delay_seconds: float = Field(default=5.0, ge=0, description="Seconds to wait between retries.")

    @field_validator("checksum")
    def validate_checksum(cls, v: Optional[str]) -> Optional[str]:
        """Validate that checksum is in the correct format."""
        if v is not None and not v.startswith("sha256:"):
            raise ValueError("Checksum must be in format 'sha256:<hex_digest>'")
        return v

    @model_validator(mode="after")
    def validate_unpack_format(self) -> "AssetConfig":
        """Validate that unpack_format is present if unpack is True."""
        if self.unpack and not self.unpack_format:
            raise ValueError("unpack_format is required when unpack is True")
        return self


class AssetSettings(BaseModel):
    """Settings for asset management."""

    cache_dir: Optional[Path] = None
