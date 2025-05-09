"""Asset management configuration models for OpenMAS."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator


class AssetSourceConfig(BaseModel):
    """Configuration for an asset source."""

    type: Literal["http", "hf", "local"]
    url: Optional[str] = None
    repo_id: Optional[str] = None
    filename: Optional[str] = None
    revision: Optional[str] = None
    path: Optional[Path] = None

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
    description: Optional[str] = None

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
