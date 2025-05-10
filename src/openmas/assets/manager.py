"""Asset management functionality for OpenMAS."""

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from openmas.assets.config import AssetConfig
from openmas.assets.downloaders import get_downloader_for_source
from openmas.assets.exceptions import (
    AssetConfigurationError,
    AssetDownloadError,
    AssetUnpackError,
    AssetVerificationError,
)
from openmas.assets.utils import asset_lock, async_asset_lock, unpack_archive, verify_checksum
from openmas.config import ProjectConfig
from openmas.logging import get_logger

logger = get_logger(__name__)


class AssetManager:
    """Manages downloading, caching, and verification of assets used by agents."""

    def __init__(self, project_config: ProjectConfig):
        """Initialize the asset manager.

        Args:
            project_config: The project configuration containing asset definitions.
        """
        # Store assets by name for quick lookup
        self.assets: Dict[str, AssetConfig] = {asset.name: asset for asset in project_config.assets}

        # Determine cache directory location with fallback chain:
        # 1. OPENMAS_ASSETS_DIR environment variable
        # 2. project_config.settings.assets.cache_dir
        # 3. Default: ~/.openmas/assets/
        cache_dir = os.environ.get("OPENMAS_ASSETS_DIR")
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        elif project_config.settings and project_config.settings.assets and project_config.settings.assets.cache_dir:
            self.cache_dir = project_config.settings.assets.cache_dir
        else:
            self.cache_dir = Path.home() / ".openmas" / "assets"

        # Ensure cache directory and locks directory exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir = self.cache_dir / ".locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)

        # We're no longer initializing downloaders directly here
        # Instead, we'll use get_downloader_for_source to get the appropriate downloader
        # when needed

    def check_asset_status(self, asset_config: AssetConfig) -> Dict[str, Any]:
        """Check the status of an asset in the cache.

        Args:
            asset_config: The asset configuration to check.

        Returns:
            Dictionary with status information:
                - exists: Whether the asset exists in the cache
                - verified: Whether the asset passes verification (if applicable)
                - path: Path to the cached asset (if it exists)
        """
        asset_dir = self._get_cache_path_for_asset(asset_config)
        metadata_path = asset_dir / ".asset_info.json"

        # Determine the expected filename
        if asset_config.source.filename:
            filename = asset_config.source.filename
        elif asset_config.source.url and asset_config.source.type == "http":
            # Use the last part of the URL as the filename
            filename = asset_config.source.url.split("/")[-1]
        else:
            # Use a default filename
            filename = "asset"

        # The final path where we expect the asset to be
        final_asset_path = asset_dir / filename if not asset_config.unpack else asset_dir

        # Check if the asset exists in cache
        exists = final_asset_path.exists() and metadata_path.exists()
        verified = False

        if exists and asset_config.checksum:
            # Check if the asset is verified
            verified = self.verify_asset(asset_config, final_asset_path)
        elif exists:
            # If no checksum is specified, consider it verified if it exists
            verified = True

        return {
            "exists": exists,
            "verified": verified,
            "path": final_asset_path if exists else None,
        }

    async def get_asset_path(self, asset_name: str, force_download: bool = False) -> Path:
        """Get the path to a cached asset, downloading it if necessary.

        This method handles the complete asset retrieval workflow:
        1. Check if the asset is already in the cache
        2. If not, download it (with retries if configured)
        3. Verify the asset checksum if specified
        4. Unpack the asset if specified
        5. Return the path to the asset

        Args:
            asset_name: The name of the asset to retrieve.
            force_download: If True, re-download the asset even if it exists in cache.

        Returns:
            Path to the cached asset.

        Raises:
            KeyError: If the asset name is not found in the project configuration.
            AssetDownloadError: If there is an error downloading the asset.
            AssetVerificationError: If the asset fails checksum verification.
            AssetUnpackError: If there is an error unpacking the asset.
        """
        if asset_name not in self.assets:
            raise KeyError(f"Asset '{asset_name}' not found in project configuration")

        asset_config = self.assets[asset_name]
        asset_dir = self._get_cache_path_for_asset(asset_config)
        lock_path = self._get_lock_path_for_asset(asset_config)
        metadata_path = asset_dir / ".asset_info.json"

        # Determine the expected filename (and downloaded filename)
        if asset_config.source.filename:
            filename = asset_config.source.filename
        elif asset_config.source.url and asset_config.source.type == "http":
            # Use the last part of the URL as the filename
            filename = asset_config.source.url.split("/")[-1]
        else:
            # Use a default filename
            filename = "asset"

        # The final path where we expect the asset to be, either unpacked or as-is
        if not asset_config.unpack:
            # Regular case: downloaded file with no unpacking
            final_asset_path = asset_dir / filename
        elif asset_config.unpack and asset_config.unpack_destination_is_file:
            # Unpacked archive containing a single file we want to access directly
            # The actual file path will be determined in unpack_asset
            # For now, we set final_asset_path to the asset_dir, and we'll update it
            # with the actual file path after unpacking
            final_asset_path = asset_dir
            # We'll need to check files in this directory after unpacking
        else:
            # Unpacked archive with content directory structure
            final_asset_path = asset_dir

        # Check if we need to download or unpack
        need_download = force_download

        # Check if metadata exists and matches our configuration
        if not force_download and metadata_path.exists() and final_asset_path.exists():
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                # Verify that metadata matches our expectations
                if (
                    metadata.get("name") != asset_config.name
                    or metadata.get("version") != asset_config.version
                    or metadata.get("source_type") != asset_config.source.type
                ):
                    logger.warning(
                        f"Asset metadata mismatch for '{asset_name}'. "
                        f"Expected {asset_config.name}/{asset_config.version}/{asset_config.source.type}, "
                        f"got {metadata.get('name')}/{metadata.get('version')}/{metadata.get('source_type')}"
                    )
                    need_download = True
            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning(f"Asset metadata file for '{asset_name}' is invalid or missing")
                need_download = True
        else:
            need_download = True

        # Try to lock and download if necessary
        async with async_asset_lock(lock_path):
            # Re-check after acquiring the lock
            if not force_download and metadata_path.exists() and final_asset_path.exists() and not need_download:
                # Verify the asset if a checksum is provided
                if asset_config.checksum:
                    # If this is an unpacked file destination, we may need to find the actual file first
                    asset_to_verify = final_asset_path
                    if asset_config.unpack and asset_config.unpack_destination_is_file:
                        # If we have an unpacked file as a destination, we need to find which file to verify
                        # Look for files in the asset directory
                        content_files = [f for f in asset_dir.glob("*") if not f.name.startswith(".") and f.is_file()]
                        if content_files:
                            asset_to_verify = content_files[0]
                            final_asset_path = asset_to_verify  # Update final path
                            logger.debug(f"Using previously unpacked file for verification: {asset_to_verify}")

                    if not self.verify_asset(asset_config, asset_to_verify):
                        logger.warning(f"Asset '{asset_name}' failed checksum verification. Removing downloaded file.")
                        if asset_to_verify.exists():
                            if asset_to_verify.is_dir():
                                shutil.rmtree(asset_to_verify)
                            else:
                                asset_to_verify.unlink()
                        raise AssetVerificationError(
                            f"Asset '{asset_name}' failed checksum verification. " f"Expected: {asset_config.checksum}"
                        )

            # Check for unpacked marker
            if asset_config.unpack:
                # Determine the appropriate marker path based on unpack_destination_is_file
                if asset_config.unpack_destination_is_file:
                    # For file unpacking, the marker is in the asset directory
                    unpacked_marker = asset_dir / ".unpacked"
                else:
                    # For directory unpacking, the marker is in the final_asset_path
                    unpacked_marker = final_asset_path / ".unpacked"

                # Check if marker exists and if the final_asset_path exists
                if not unpacked_marker.exists() and final_asset_path.exists():
                    logger.info(f"Asset '{asset_name}' found but unpacking not complete")
                    need_download = True

            # Download if needed
            if need_download:
                logger.info(f"Downloading asset '{asset_name}'{' (forced)' if force_download else ''}")

                # Create asset directory if it doesn't exist
                asset_dir.mkdir(parents=True, exist_ok=True)

                # If force_download, remove existing files
                if force_download and final_asset_path.exists():
                    if final_asset_path.is_dir():
                        shutil.rmtree(final_asset_path)
                    else:
                        final_asset_path.unlink()
                    logger.info(f"Removed existing asset '{asset_name}' for forced download")

                # Initialize retry variables
                max_attempts = asset_config.retries + 1  # +1 for the initial attempt
                attempts = 0
                downloaded_path = None

                # Retry loop for download
                while attempts < max_attempts:
                    attempts += 1
                    downloaded_path = None
                    try:
                        logger.info(f"Download attempt {attempts}/{max_attempts} for asset '{asset_name}'")
                        downloaded_path = await self.download_asset(asset_config)

                        # Verify the checksum if provided
                        if asset_config.checksum:
                            if not self.verify_asset(asset_config, downloaded_path):
                                # If checksum fails, clean up and retry or fail
                                logger.warning(
                                    f"Asset '{asset_name}' failed checksum verification. Removing downloaded file."
                                )
                                if downloaded_path and downloaded_path.exists():
                                    downloaded_path.unlink()
                                raise AssetVerificationError(
                                    f"Asset '{asset_name}' failed checksum verification. "
                                    f"Expected: {asset_config.checksum}"
                                )
                            logger.info(f"Asset '{asset_name}' checksum verified successfully")

                        # If we get here, download and verification succeeded
                        break

                    except (AssetDownloadError, AssetVerificationError) as e:
                        # Clean up failed download if it exists
                        if downloaded_path and downloaded_path.exists():
                            try:
                                if downloaded_path.is_dir():
                                    shutil.rmtree(downloaded_path)
                                else:
                                    downloaded_path.unlink()
                            except (OSError, PermissionError) as unlink_error:
                                logger.warning(f"Could not delete failed download: {unlink_error}")

                        # Log the error and wait before retrying
                        logger.warning(
                            f"Download attempt {attempts}/{max_attempts} failed for asset '{asset_name}': {str(e)}"
                        )

                        # Handle errors that can trigger a retry
                        if attempts >= max_attempts:
                            logger.error(f"All {max_attempts} download attempts failed for asset '{asset_name}'")
                            source_info = getattr(asset_config.source, "url", None) or getattr(
                                asset_config.source, "repo_id", None
                            )

                            # Include the original error message in the new exception
                            error_message = f"Failed to download asset '{asset_name}' after {max_attempts} attempts"
                            if isinstance(e, AssetVerificationError):
                                error_message += f": {str(e)}"
                            else:
                                # Use consistent format expected by tests
                                error_message = (
                                    f"Failed to download asset '{asset_name}' after {max_attempts} attempts: {str(e)}"
                                )

                            raise AssetDownloadError(
                                error_message, source_type=asset_config.source.type, source_info=source_info
                            )

                        # If we still have retries left, add a delay and continue
                        retry_delay = asset_config.retry_delay_seconds
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)

                # Check if all download attempts failed and we didn't break out of the loop
                if attempts >= max_attempts and not downloaded_path:
                    logger.error(
                        f"All {max_attempts} download attempts failed for asset '{asset_name}' with no path returned"
                    )
                    source_info = getattr(asset_config.source, "url", None) or getattr(
                        asset_config.source, "repo_id", None
                    )
                    # Make sure to include the original error message if available
                    last_error_msg = ""
                    for attempt in range(max_attempts, 0, -1):
                        error_log = f"Download attempt {attempt}/{max_attempts} failed for asset '{asset_name}'"
                        if error_log in str(logger.handlers):
                            last_error_msg = str(logger.handlers).split(error_log)[1].split("]")[0].strip(": ")
                            break

                    error_message = f"Failed to download asset '{asset_name}' after {max_attempts} attempts"
                    if last_error_msg:
                        error_message += f": {last_error_msg}"

                    raise AssetDownloadError(
                        error_message, source_type=asset_config.source.type, source_info=source_info
                    )

                # Unpack if needed
                if asset_config.unpack and downloaded_path is not None:
                    unpacked_path = self.unpack_asset(asset_config, downloaded_path, asset_dir)

                    # If unpack_destination_is_file is True, update final_asset_path to the actual file
                    if asset_config.unpack_destination_is_file and unpacked_path != asset_dir:
                        final_asset_path = unpacked_path
                        logger.debug(f"Asset '{asset_name}' unpacked with destination_is_file=True: {final_asset_path}")
                        # For a file, the marker should be in the parent directory
                        unpacked_marker = asset_dir / ".unpacked"
                    else:
                        # For a directory, the marker goes in the directory itself
                        unpacked_marker = final_asset_path / ".unpacked"

                    # Create a marker file to indicate successful unpacking
                    unpacked_marker.touch()

                # Write metadata file
                metadata = {
                    "name": asset_config.name,
                    "version": asset_config.version,
                    "asset_type": asset_config.asset_type,
                    "source_type": asset_config.source.type,
                    "checksum": asset_config.checksum,
                    "unpack": asset_config.unpack,
                    "unpack_format": asset_config.unpack_format,
                    "description": asset_config.description,
                }

                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)

                logger.debug(f"Wrote asset metadata to {metadata_path}")
            else:
                logger.info(f"Asset '{asset_name}' found in cache")

        return final_asset_path

    async def download_asset(self, asset_config: AssetConfig) -> Path:
        """Download an asset to the cache directory.

        Args:
            asset_config: The configuration for the asset to download.

        Returns:
            Path to the downloaded asset.

        Raises:
            AssetConfigurationError: If the source configuration is invalid.
            AssetDownloadError: If there is an error downloading the asset.
        """
        # Determine the target path for the asset
        target_path = self._get_cache_path_for_asset(asset_config)
        source_config = asset_config.source

        # Ensure parent directory exists
        target_path.mkdir(parents=True, exist_ok=True)

        # Determine the filename for the download
        if source_config.filename:
            download_filename = source_config.filename
        elif source_config.url and source_config.type == "http":
            # Use the last part of the URL as the filename
            download_filename = source_config.url.split("/")[-1]
        else:
            # Use a default filename
            download_filename = "asset"

        download_path = target_path / download_filename

        logger.info(f"Downloading asset '{asset_config.name}' (version: {asset_config.version})")

        try:
            # Get the appropriate downloader based on the source type
            downloader = get_downloader_for_source(source_config)

            # Download the asset
            await downloader.download(source_config, download_path)

            # Return the path to the downloaded asset
            return download_path

        except (AssetConfigurationError, AssetDownloadError):
            # Re-raise these exceptions as they already have appropriate context
            raise
        except Exception as e:
            # Wrap other exceptions in an AssetDownloadError
            raise AssetDownloadError(
                f"Unexpected error downloading asset '{asset_config.name}': {str(e)}",
                source_type=source_config.type,
                source_info=str(source_config),
            ) from e

    def verify_asset(self, asset_config: AssetConfig, asset_path: Path) -> bool:
        """Verify an asset's integrity using its checksum.

        Args:
            asset_config: The asset configuration containing the checksum.
            asset_path: The path to the asset to verify.

        Returns:
            True if the asset is valid, False otherwise.

        Raises:
            AssetVerificationError: If verification fails due to an error.
            ValueError: If the checksum format is invalid.
        """
        if not asset_config.checksum:
            logger.info(f"No checksum specified for asset '{asset_config.name}', skipping verification")
            return True

        logger.info(f"Verifying asset '{asset_config.name}' using checksum: {asset_config.checksum}")

        try:
            result = verify_checksum(asset_path, asset_config.checksum)
            if result:
                logger.info(f"Asset '{asset_config.name}' verified successfully")
            else:
                logger.warning(
                    f"Asset '{asset_config.name}' checksum verification failed. " f"Expected: {asset_config.checksum}"
                )
            return result
        except (ValueError, AssetVerificationError, FileNotFoundError) as e:
            logger.error(f"Error verifying asset '{asset_config.name}': {str(e)}")
            raise

    def unpack_asset(self, asset_config: AssetConfig, archive_path: Path, target_dir: Path) -> Path:
        """Unpack an archived asset.

        Args:
            asset_config: The asset configuration.
            archive_path: The path to the archive file.
            target_dir: The directory to unpack the archive to.

        Returns:
            Path to the unpacked directory or file (if unpack_destination_is_file is True)

        Raises:
            AssetUnpackError: If there is an error unpacking the asset.
            ValueError: If the format is not supported.
        """
        if not asset_config.unpack:
            logger.debug(f"Asset '{asset_config.name}' is not configured for unpacking")
            return archive_path  # Just return the original archive path if unpacking is not required

        if not asset_config.unpack_format:
            raise AssetConfigurationError(
                f"Asset '{asset_config.name}' is configured for unpacking but no format is specified"
            )

        # Acquire a lock on the target directory to prevent race conditions
        lock_path = self._get_lock_path_for_asset(asset_config)
        logger.info(f"Unpacking asset '{asset_config.name}' to {target_dir}")

        unpacked_path = target_dir  # Default to returning the target directory

        try:
            with asset_lock(lock_path):
                # Check if we've already unpacked and the marker exists
                unpacked_marker = target_dir / ".unpacked"
                if unpacked_marker.exists():
                    logger.info(f"Asset '{asset_config.name}' is already unpacked")

                    # If unpack_destination_is_file is True, attempt to find the single file
                    if asset_config.unpack_destination_is_file:
                        # If we've already unpacked, try to find the file we want
                        files = list(target_dir.glob("*"))
                        content_files = [f for f in files if not f.name.startswith(".") and f.is_file()]

                        if content_files:
                            # Use the first file as the destination
                            unpacked_path = content_files[0]
                            logger.debug(f"Using previously unpacked file: {unpacked_path}")
                        else:
                            logger.warning(
                                f"Asset '{asset_config.name}' is marked as unpacked "
                                "with unpack_destination_is_file=True, "
                                f"but no suitable files found in {target_dir}"
                            )

                    return unpacked_path

                # Ensure the target directory exists
                target_dir.mkdir(parents=True, exist_ok=True)

                # Unpack the archive
                unpacked_path = unpack_archive(
                    archive_path,
                    target_dir,
                    asset_config.unpack_format,
                    destination_is_file=asset_config.unpack_destination_is_file,
                )

                # Create a marker file to indicate successful unpacking
                # For file destinations, place the marker in the parent directory
                if asset_config.unpack_destination_is_file and unpacked_path != target_dir:
                    # Place marker in the parent directory
                    unpacked_marker = target_dir / ".unpacked"
                else:
                    # For directory unpacking, place marker in the directory itself
                    unpacked_marker = target_dir / ".unpacked"

                unpacked_marker.touch()

                # Optionally, delete the archive file to save space
                archive_path.unlink()

                logger.info(f"Successfully unpacked asset '{asset_config.name}' to {unpacked_path}")
                return unpacked_path
        except Exception as e:
            # Clean up potentially partially unpacked files
            if not (target_dir / ".unpacked").exists():
                try:
                    # Delete all contents of the target directory except the archive
                    for item in target_dir.iterdir():
                        if item != archive_path:
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                except Exception:
                    logger.warning(f"Failed to clean up after unpacking error for asset '{asset_config.name}'")

            if isinstance(e, (AssetUnpackError, ValueError)):
                raise
            else:
                raise AssetUnpackError(f"Error unpacking asset '{asset_config.name}': {str(e)}") from e

    def _get_cache_path_for_asset(self, asset_config: AssetConfig) -> Path:
        """Get the cache path for an asset.

        Args:
            asset_config: The asset configuration.

        Returns:
            Path to the asset's cache directory.
        """
        # Create a path structure based on asset type, name, and version
        asset_type = asset_config.asset_type or "model"  # Default to "model" if not specified
        asset_name = asset_config.name
        asset_version = asset_config.version or "latest"

        # Return the full path to the asset directory
        return self.cache_dir / asset_type / asset_name / asset_version

    def _get_lock_path_for_asset(self, asset_config: AssetConfig) -> Path:
        """Get the lock file path for an asset.

        Args:
            asset_config: The asset configuration.

        Returns:
            Path to the asset's lock file.
        """
        # Create a unique filename based on the asset name and version
        asset_name = asset_config.name
        asset_version = asset_config.version or "latest"
        lock_filename = f"{asset_name}_{asset_version}.lock"

        # Return the full path to the lock file
        return self.locks_dir / lock_filename

    def clear_asset_cache(self, asset_name: str) -> bool:
        """Clear a specific asset from the cache.

        Args:
            asset_name: The name of the asset to clear.

        Returns:
            bool: True if the asset was cleared, False if it wasn't found in the cache.

        Raises:
            KeyError: If the asset name is not found in the project configuration.
        """
        # Check if asset exists in configuration
        if asset_name not in self.assets:
            raise KeyError(f"Asset '{asset_name}' not found in project configuration")

        asset_config = self.assets[asset_name]
        asset_dir = self._get_cache_path_for_asset(asset_config)
        lock_path = self._get_lock_path_for_asset(asset_config)

        # Check if the asset directory exists
        if not asset_dir.exists():
            logger.info(f"Asset '{asset_name}' not found in cache at '{asset_dir}'")
            return True

        # Lock to ensure we don't clear during a download
        with asset_lock(lock_path):
            logger.info(f"Clearing cache for asset '{asset_name}' at '{asset_dir}'")

            # Remove the directory
            try:
                if asset_dir.is_dir():
                    shutil.rmtree(asset_dir)
                else:
                    asset_dir.unlink()
                logger.info(f"Cache for asset '{asset_name}' cleared successfully")
                return True
            except Exception as e:
                logger.warning(f"Error clearing cache for asset '{asset_name}': {e}")
                return False

    def clear_entire_cache(self, exclude_hf_cache: bool = True) -> None:
        """Clear the entire asset cache.

        Args:
            exclude_hf_cache: If True, preserve the shared Hugging Face cache.
        """
        logger.info(f"Clearing entire asset cache at '{self.cache_dir}'")

        # Get list of all items in the cache directory
        if not self.cache_dir.exists():
            logger.info(f"Cache directory '{self.cache_dir}' does not exist")
            return

        for item in self.cache_dir.iterdir():
            # Skip the locks directory
            if item.name == ".locks":
                continue

            # Skip the HF cache if requested
            if exclude_hf_cache and (item.name == ".hf_cache" or item.name == "huggingface"):
                logger.debug(f"Skipping {item.name} directory as requested")
                continue

            # Remove the item
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                logger.debug(f"Removed '{item}'")
            except Exception as e:
                logger.warning(f"Error removing '{item}': {e}")

        logger.info("Asset cache cleared successfully")
