"""Downloader implementations for the asset management module."""

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Type

import httpx

from openmas.assets.config import AssetSourceConfig
from openmas.assets.exceptions import AssetAuthenticationError, AssetConfigurationError, AssetDownloadError
from openmas.logging import get_logger

logger = get_logger(__name__)

# Try to import tqdm, but make it optional
TQDM_AVAILABLE = False
try:
    from tqdm import tqdm  # type: ignore

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

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
            AssetAuthenticationError: If authentication is required but the token is not available
        """
        if source_config.type != "http":
            raise AssetConfigurationError(f"Expected source type 'http', got '{source_config.type}'")

        if not source_config.url:
            raise AssetConfigurationError("URL is required for HTTP downloads")

        url = source_config.url
        logger.info(f"Downloading asset from {url} to {target_path}")

        # Ensure the parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare headers if authentication is specified
        headers = {}
        if source_config.authentication and source_config.authentication.http:
            http_auth = source_config.authentication.http
            token_env_var = http_auth.token_env_var
            token = os.environ.get(token_env_var)

            if not token:
                error_msg = f"HTTP authentication token environment variable '{token_env_var}' not found or empty"
                logger.error(error_msg)
                # We'll raise an exception if strict authentication is required
                if kwargs.get("strict_authentication", False):
                    raise AssetAuthenticationError(
                        error_msg,
                        source_type="http",
                        source_info=url,
                        token_env_var=token_env_var,
                    )
                else:
                    logger.warning(
                        "Authentication token not found, but proceeding with download attempt. "
                        "Set strict_authentication=True to fail instead."
                    )
            else:
                # Apply the authentication scheme if one is specified
                if http_auth.scheme:
                    auth_value = f"{http_auth.scheme} {token}"
                else:
                    auth_value = token

                headers[http_auth.header_name] = auth_value
                logger.debug(f"Using authentication with header: {http_auth.header_name}")

        try:
            # Use httpx for async HTTP requests
            async with httpx.AsyncClient(follow_redirects=True) as client:
                async with client.stream("GET", url, headers=headers, timeout=30.0) as response:
                    if response.status_code >= 400:
                        error_message = f"HTTP error {response.status_code}: {response.reason_phrase}"
                        # Provide more context for auth-related errors
                        if response.status_code in (401, 403):
                            if source_config.authentication and source_config.authentication.http:
                                error_message += (
                                    f". This might be an authentication issue. "
                                    f"Check that the token in '{source_config.authentication.http.token_env_var}' "
                                    f"is correct and has appropriate permissions."
                                )
                            else:
                                error_message += (
                                    ". This resource may require authentication. "
                                    "Consider adding authentication details to your asset configuration."
                                )
                            # Raise a specific authentication error for 401/403 responses
                            raise AssetAuthenticationError(
                                error_message,
                                source_type="http",
                                source_info=url,
                                token_env_var=(
                                    source_config.authentication.http.token_env_var
                                    if source_config.authentication and source_config.authentication.http
                                    else None
                                ),
                            )
                        else:
                            raise AssetDownloadError(
                                error_message,
                                source_type="http",
                                source_info=url,
                            )

                    # Get total size if available
                    total_size = int(response.headers.get("content-length", "0")) or None
                    if total_size:
                        logger.info(f"Total asset size: {total_size / (1024 * 1024):.2f} MB")

                    # Determine if we should use progress reporting
                    use_progress_reporting = source_config.progress_report
                    progress_interval_mb = getattr(
                        source_config, "progress_report_interval_mb", self.progress_interval_mb
                    )
                    progress_interval_bytes = int(progress_interval_mb * 1024 * 1024)

                    # Determine if we should use tqdm progress bar (for interactive terminal)
                    use_tqdm = use_progress_reporting and TQDM_AVAILABLE and total_size and sys.stdout.isatty()

                    # Stream the response to the file
                    with open(target_path, "wb") as f:
                        downloaded = 0
                        next_log = progress_interval_bytes

                        if use_tqdm:
                            # Use tqdm for nice progress bars in terminal
                            with tqdm(
                                total=total_size,
                                unit="B",
                                unit_scale=True,
                                desc="Downloading asset",
                                leave=False,
                            ) as pbar:
                                async for chunk in response.aiter_bytes(self.chunk_size):
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    pbar.update(len(chunk))
                        else:
                            # Use interval-based logging for non-interactive terminals
                            async for chunk in response.aiter_bytes(self.chunk_size):
                                f.write(chunk)
                                downloaded += len(chunk)

                                # Log progress at intervals if progress reporting is enabled
                                if use_progress_reporting and total_size and downloaded >= next_log:
                                    progress = downloaded / total_size * 100
                                    logger.info(
                                        f"Download progress: {downloaded / (1024 * 1024):.2f} MB "
                                        f"/ {total_size / (1024 * 1024):.2f} MB ({progress:.1f}%)"
                                    )
                                    next_log = downloaded + progress_interval_bytes

                    # Log final download completion
                    if use_progress_reporting:
                        logger.info(f"Download complete: {downloaded / (1024 * 1024):.2f} MB")

        except httpx.RequestError as e:
            # Clean up partial download
            if target_path.exists():
                target_path.unlink()
            raise AssetDownloadError(f"Error downloading asset: {str(e)}", source_type="http", source_info=url) from e
        except AssetAuthenticationError:
            # Clean up partial download
            if target_path.exists():
                target_path.unlink()
            # Re-raise the authentication error
            raise
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
        self.token = token

    def _download(
        self, repo_id: str, filename: Optional[str], revision: str, token: Optional[str], target_path: Path
    ) -> Path:
        """Execute the Hugging Face Hub download in a separate thread.

        Args:
            repo_id: Hugging Face Hub repository ID
            filename: Filename to download from the repository
            revision: Repository revision/branch to use
            token: Authentication token for the Hugging Face Hub
            target_path: Path where the asset should be saved

        Returns:
            Path: Path to the downloaded asset

        Raises:
            Any exceptions from the underlying hf_hub_download will be propagated
        """
        if HF_HUB_DOWNLOAD is None:
            raise ImportError(
                "Hugging Face Hub is not installed. "
                "Please install the huggingface_hub package with: "
                "pip install huggingface_hub"
            )

        # Ensure the parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a temporary cache directory
        cache_dir = target_path.parent / ".hf-cache"
        cache_dir.mkdir(exist_ok=True)

        try:
            # Download to temporary location
            downloaded_path = HF_HUB_DOWNLOAD(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                token=token,
                cache_dir=cache_dir,
                local_dir=target_path.parent,
                local_dir_use_symlinks=False,
            )

            # Move to final location if needed
            downloaded_path = Path(downloaded_path)
            if downloaded_path != target_path:
                if target_path.exists():
                    target_path.unlink()
                shutil.move(downloaded_path, target_path)

            return target_path

        finally:
            # Clean up temporary cache directory
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                except Exception as e:
                    # Just log the error but don't fail the download
                    logger.warning(f"Failed to clean up temporary cache directory: {e}")

    async def download(self, source_config: AssetSourceConfig, target_path: Path, **kwargs: Any) -> None:
        """Download an asset from Hugging Face Hub to the target path.

        Args:
            source_config: Configuration for the Hugging Face Hub source
            target_path: Path where the asset should be downloaded
            **kwargs: Additional keyword arguments for the downloader

        Raises:
            AssetConfigurationError: If the source configuration is invalid
            AssetDownloadError: If there is an error downloading the asset
            AssetAuthenticationError: If authentication is required but the token is not available
        """
        if source_config.type != "hf":
            raise AssetConfigurationError(f"Expected source type 'hf', got '{source_config.type}'")

        if not source_config.repo_id:
            raise AssetConfigurationError("repo_id is required for Hugging Face Hub downloads")

        repo_id = source_config.repo_id
        filename = source_config.filename
        revision = source_config.revision or "main"

        # Get authentication token from source_config if available,
        # otherwise use the one provided to the constructor or fall back to environment variables
        token = self.token

        # If authentication details are provided, extract the token from the specified environment variable
        token_env_var = None
        if source_config.authentication and source_config.authentication.hf:
            token_env_var = source_config.authentication.hf.token_env_var
            env_token = os.environ.get(token_env_var)
            if env_token:
                token = env_token
                logger.debug(f"Using token from environment variable '{token_env_var}'")
            else:
                error_msg = (
                    f"Hugging Face authentication token environment variable '{token_env_var}' not found or empty."
                )
                logger.warning(f"{error_msg} " "Download may fail if authentication is required.")
                # Check if strict authentication is required and fail early
                if kwargs.get("strict_authentication", False):
                    raise AssetAuthenticationError(
                        error_msg,
                        source_type="hf",
                        source_info=f"{repo_id}/{filename}",
                        token_env_var=token_env_var,
                    )

        # Determine if we should use progress reporting
        use_progress_reporting = source_config.progress_report

        # Configure HF Hub progress display based on user preference
        original_hf_progress_setting = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")

        try:
            # Disable HF Hub progress bars if the user has disabled progress reporting
            if not use_progress_reporting:
                os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
                logger.debug(
                    f"Disabled Hugging Face Hub progress bars as per configuration for asset "
                    f"'{repo_id}/{filename or ''}'"
                )
            elif use_progress_reporting:
                # Ensure HF Hub progress bars are enabled if user wants progress reporting
                if "HF_HUB_DISABLE_PROGRESS_BARS" in os.environ:
                    del os.environ["HF_HUB_DISABLE_PROGRESS_BARS"]
                logger.info(f"Downloading asset '{repo_id}/{filename}' (progress display managed by Hugging Face Hub)")

            # Use an executor to run synchronous hf_hub_download in a separate thread
            loop = asyncio.get_running_loop()
            try:
                downloaded_path = await loop.run_in_executor(
                    None, lambda: self._download(repo_id, filename, revision, token, target_path)
                )
                logger.info(f"Successfully downloaded asset from Hugging Face Hub to {downloaded_path}")
                return
            except Exception as e:
                error_msg = str(e)

                # Check for authentication errors
                if "401" in error_msg or "unauthorized" in error_msg.lower():
                    auth_context = "no authentication was provided"
                    if token:
                        auth_context = "the provided token may be invalid or expired"
                    elif token_env_var:
                        auth_context = f"token from '{token_env_var}' may be invalid or expired"

                    raise AssetAuthenticationError(
                        f"Authentication error accessing Hugging Face Hub resource: {error_msg}. {auth_context}",
                        source_type="hf",
                        source_info=f"{repo_id}/{filename}",
                        token_env_var=token_env_var,
                    )
                elif "404" in error_msg or "not found" in error_msg.lower():
                    raise AssetDownloadError(
                        f"Resource not found on Hugging Face Hub: {error_msg}",
                        source_type="hf",
                        source_info=f"{repo_id}/{filename}",
                    )
                else:
                    raise AssetDownloadError(
                        f"Error downloading from Hugging Face Hub: {error_msg}",
                        source_type="hf",
                        source_info=f"{repo_id}/{filename}",
                    )
        finally:
            # Restore original HF Hub progress setting
            if original_hf_progress_setting is not None:
                os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = original_hf_progress_setting
            elif "HF_HUB_DISABLE_PROGRESS_BARS" in os.environ:
                del os.environ["HF_HUB_DISABLE_PROGRESS_BARS"]


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

    # Log a warning if authentication might be needed but not provided
    if source_config.type == "hf" and not source_config.authentication:
        logger.warning(
            "No authentication provided for Hugging Face Hub source. "
            "This may fail if the repository requires authentication. "
            "Consider adding authentication details to the asset configuration."
        )
    elif source_config.type == "http" and not source_config.authentication:
        logger.debug(
            "No authentication provided for HTTP source. "
            "This will work for public resources, but may fail if authentication is required."
        )

    try:
        return downloaders[source_config.type]()
    except ImportError as e:
        if source_config.type == "hf":
            raise AssetConfigurationError(
                "Hugging Face Hub is not installed. Please install it with: " "pip install huggingface_hub"
            ) from e
        raise
