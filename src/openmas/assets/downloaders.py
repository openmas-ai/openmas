"""Downloader implementations for the asset management module."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Type

import httpx

from openmas.assets.config import AssetSourceConfig
from openmas.assets.exceptions import AssetConfigurationError, AssetDownloadError
from openmas.logging import get_logger

logger = get_logger(__name__)

# Try to import huggingface_hub, but make it optional
HF_HUB_DOWNLOAD = None
try:
    from huggingface_hub import hf_hub_download  # type: ignore

    HF_HUB_DOWNLOAD = hf_hub_download
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False


class BaseDownloader:
    """Base class for asset downloaders."""

    async def download(self, source_config: AssetSourceConfig, target_path: Path, **kwargs: Any) -> None:
        """Download an asset from the specified source to the target path.

        Args:
            source_config: Configuration for the source
            target_path: Path where the asset should be downloaded
            **kwargs: Additional keyword arguments for the downloader

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement download()")


class HttpDownloader(BaseDownloader):
    """Downloader for HTTP sources."""

    def __init__(self, chunk_size: int = 8192, progress_interval_mb: int = 10):
        """Initialize the HTTP downloader.

        Args:
            chunk_size: Size of chunks to download at a time (bytes)
            progress_interval_mb: Interval for logging progress (megabytes)
        """
        self.chunk_size = chunk_size
        self.progress_interval_mb = progress_interval_mb
        self.progress_interval_bytes = progress_interval_mb * 1024 * 1024

    async def download(self, source_config: AssetSourceConfig, target_path: Path, **kwargs: Any) -> None:
        """Download an asset from an HTTP source to the target path.

        Args:
            source_config: Configuration for the HTTP source
            target_path: Path where the asset should be downloaded
            **kwargs: Additional keyword arguments for the downloader

        Raises:
            AssetConfigurationError: If the source configuration is invalid
            AssetDownloadError: If there is an error downloading the asset
        """
        if source_config.type != "http":
            raise AssetConfigurationError(f"Expected source type 'http', got '{source_config.type}'")

        if not source_config.url:
            raise AssetConfigurationError("URL is required for HTTP downloads")

        url = source_config.url
        logger.info(f"Downloading asset from {url} to {target_path}")

        # Ensure the parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use httpx for async HTTP requests
            async with httpx.AsyncClient(follow_redirects=True) as client:
                async with client.stream("GET", url, timeout=30.0) as response:
                    if response.status_code >= 400:
                        raise AssetDownloadError(
                            f"HTTP error {response.status_code}: {response.reason_phrase}",
                            source_type="http",
                            source_info=url,
                        )

                    # Get total size if available
                    total_size = int(response.headers.get("content-length", "0")) or None
                    if total_size:
                        logger.info(f"Total asset size: {total_size / (1024 * 1024):.2f} MB")

                    # Stream the response to the file
                    with open(target_path, "wb") as f:
                        downloaded = 0
                        next_log = self.progress_interval_bytes

                        async for chunk in response.aiter_bytes(self.chunk_size):
                            f.write(chunk)
                            downloaded += len(chunk)

                            # Log progress at intervals
                            if total_size and downloaded >= next_log:
                                progress = downloaded / total_size * 100
                                logger.info(
                                    f"Download progress: {downloaded / (1024 * 1024):.2f} MB "
                                    f"/ {total_size / (1024 * 1024):.2f} MB ({progress:.1f}%)"
                                )
                                next_log = downloaded + self.progress_interval_bytes

                    logger.info(f"Download complete: {downloaded / (1024 * 1024):.2f} MB")

        except httpx.RequestError as e:
            # Clean up partial download
            if target_path.exists():
                target_path.unlink()
            raise AssetDownloadError(f"Error downloading asset: {str(e)}", source_type="http", source_info=url) from e
        except Exception as e:
            # Clean up partial download
            if target_path.exists():
                target_path.unlink()
            raise AssetDownloadError(
                f"Unexpected error downloading asset: {str(e)}",
                source_type="http",
                source_info=url,
            ) from e


class HfDownloader(BaseDownloader):
    """Downloader for Hugging Face Hub sources."""

    def __init__(self, token: Optional[str] = None):
        """Initialize the Hugging Face downloader.

        Args:
            token: Optional Hugging Face API token for accessing private models
        """
        if not HF_AVAILABLE:
            raise ImportError(
                "Hugging Face Hub is not installed. "
                "Please install the huggingface_hub package with: "
                "pip install huggingface_hub"
            )
        self.token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

    async def download(self, source_config: AssetSourceConfig, target_path: Path, **kwargs: Any) -> None:
        """Download an asset from Hugging Face Hub to the target path.

        Args:
            source_config: Configuration for the Hugging Face Hub source
            target_path: Path where the asset should be downloaded
            **kwargs: Additional keyword arguments for the downloader

        Raises:
            AssetConfigurationError: If the source configuration is invalid
            AssetDownloadError: If there is an error downloading the asset
        """
        if source_config.type != "hf":
            raise AssetConfigurationError(f"Expected source type 'hf', got '{source_config.type}'")

        if not source_config.repo_id:
            raise AssetConfigurationError("repo_id is required for Hugging Face Hub downloads")

        repo_id = source_config.repo_id
        filename = source_config.filename
        revision = source_config.revision or "main"

        logger.info(
            f"Downloading asset from Hugging Face Hub: {repo_id}/{filename or '*'} "
            f"(revision: {revision}) to {target_path}"
        )

        # Ensure the parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Create a cache config that will download directly to our target
            # We can't do this directly with hf_hub_download, so we'll download to a temp location
            # and then move it to the target path
            cache_dir = target_path.parent / ".hf-cache"
            cache_dir.mkdir(exist_ok=True)

            # Since hf_hub_download is synchronous, run it in a thread pool
            def _download() -> Any:
                if HF_HUB_DOWNLOAD is None:
                    raise ImportError(
                        "Hugging Face Hub is not installed. "
                        "Please install the huggingface_hub package with: "
                        "pip install huggingface_hub"
                    )
                return HF_HUB_DOWNLOAD(
                    repo_id=repo_id,
                    filename=filename,
                    revision=revision,
                    token=self.token,
                    cache_dir=cache_dir,
                    **kwargs,
                )

            # Run in thread pool
            downloaded_path = await asyncio.to_thread(_download)

            # Move the file to the target path
            if target_path.exists():
                target_path.unlink()
            shutil.move(downloaded_path, target_path)

            logger.info(f"Download complete: {target_path}")

            # Clean up the temporary cache directory
            if cache_dir.exists():
                shutil.rmtree(cache_dir)

        except Exception as e:
            # Clean up partial download
            if target_path.exists():
                target_path.unlink()
            raise AssetDownloadError(
                f"Error downloading asset from Hugging Face Hub: {str(e)}",
                source_type="hf",
                source_info=f"{repo_id}/{filename or '*'}",
            ) from e


class LocalFileHandler(BaseDownloader):
    """Handler for local file sources."""

    async def download(self, source_config: AssetSourceConfig, target_path: Path, **kwargs: Any) -> None:
        """Copy a local asset to the target path.

        Args:
            source_config: Configuration for the local source
            target_path: Path where the asset should be copied
            **kwargs: Additional keyword arguments for the handler

        Raises:
            AssetConfigurationError: If the source configuration is invalid
            AssetDownloadError: If there is an error copying the asset
        """
        if source_config.type != "local":
            raise AssetConfigurationError(f"Expected source type 'local', got '{source_config.type}'")

        if not source_config.path:
            raise AssetConfigurationError("path is required for local file sources")

        source_path = source_config.path
        logger.info(f"Copying local asset from {source_path} to {target_path}")

        # Ensure the path exists
        if not source_path.exists():
            raise AssetDownloadError(
                f"Local source path does not exist: {source_path}",
                source_type="local",
                source_info=str(source_path),
            )

        # Ensure the parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Handle directory vs file
            if source_path.is_dir():
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(source_path, target_path)
                logger.info(f"Copied directory: {source_path} -> {target_path}")
            else:
                if target_path.exists():
                    target_path.unlink()
                shutil.copy2(source_path, target_path)
                logger.info(f"Copied file: {source_path} -> {target_path}")
        except Exception as e:
            # Clean up partial copy
            if target_path.exists():
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
            raise AssetDownloadError(
                f"Error copying local asset: {str(e)}",
                source_type="local",
                source_info=str(source_path),
            ) from e


def get_downloader_for_source(source_config: AssetSourceConfig) -> BaseDownloader:
    """Get the appropriate downloader for a source configuration.

    Args:
        source_config: The source configuration

    Returns:
        The appropriate downloader for the source

    Raises:
        AssetConfigurationError: If the source type is unknown
    """
    downloaders: Dict[str, Type[BaseDownloader]] = {
        "http": HttpDownloader,
        "hf": HfDownloader,
        "local": LocalFileHandler,
    }

    if source_config.type not in downloaders:
        raise AssetConfigurationError(f"Unknown source type: {source_config.type}")

    try:
        return downloaders[source_config.type]()
    except ImportError as e:
        if source_config.type == "hf":
            raise AssetConfigurationError(
                "Hugging Face Hub is not installed. Please install it with: " "pip install huggingface_hub"
            ) from e
        raise
