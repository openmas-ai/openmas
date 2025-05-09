"""Asset management module for OpenMAS."""

from openmas.assets.config import AssetConfig, AssetSettings, AssetSourceConfig
from openmas.assets.downloaders import (
    BaseDownloader,
    HfDownloader,
    HttpDownloader,
    LocalFileHandler,
    get_downloader_for_source,
)
from openmas.assets.exceptions import (
    AssetConfigurationError,
    AssetDownloadError,
    AssetError,
    AssetUnpackError,
    AssetVerificationError,
)
from openmas.assets.manager import AssetManager

__all__ = [
    # Configuration
    "AssetConfig",
    "AssetSourceConfig",
    "AssetSettings",
    # Asset Manager
    "AssetManager",
    # Downloaders
    "BaseDownloader",
    "HttpDownloader",
    "HfDownloader",
    "LocalFileHandler",
    "get_downloader_for_source",
    # Exceptions
    "AssetError",
    "AssetConfigurationError",
    "AssetDownloadError",
    "AssetVerificationError",
    "AssetUnpackError",
]
