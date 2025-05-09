"""Asset management functionality for OpenMAS."""

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

    async def get_asset_path(self, asset_name: str) -> Path:
        """Get the path to a cached asset, downloading it if necessary.

        This method handles the complete asset retrieval workflow:
        1. Check if the asset is already in the cache
        2. If not, download it
        3. Verify the asset checksum if specified
        4. Unpack the asset if specified
        5. Return the path to the asset

        Args:
            asset_name: The name of the asset to retrieve.

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
        final_asset_path = asset_dir / filename

        # For unpacked assets, we need a different final path
        if asset_config.unpack:
            # The actual asset will be the unpacked directory
            final_asset_path = asset_dir

        # Check if we need to download or unpack
        need_download = False

        # Check if metadata exists and matches our configuration
        if metadata_path.exists() and final_asset_path.exists():
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
            if metadata_path.exists() and final_asset_path.exists() and not need_download:
                # Verify the asset if a checksum is provided
                if asset_config.checksum and not self.verify_asset(asset_config, final_asset_path):
                    logger.warning(
                        f"Asset '{asset_name}' failed checksum verification. " f"Expected: {asset_config.checksum}"
                    )
                    need_download = True

            # Check for unpacked marker
            if asset_config.unpack and not (final_asset_path / ".unpacked").exists() and final_asset_path.exists():
                logger.info(f"Asset '{asset_name}' found but unpacking not complete")
                need_download = True

            # Download if needed
            if need_download:
                logger.info(f"Downloading asset '{asset_name}'")

                # Create asset directory if it doesn't exist
                asset_dir.mkdir(parents=True, exist_ok=True)

                downloaded_path = await self.download_asset(asset_config)

                # Verify the checksum if provided
                if asset_config.checksum and not self.verify_asset(asset_config, downloaded_path):
                    raise AssetVerificationError(
                        f"Asset '{asset_name}' failed checksum verification. " f"Expected: {asset_config.checksum}"
                    )

                # Unpack if needed
                if asset_config.unpack:
                    self.unpack_asset(asset_config, downloaded_path, asset_dir)

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

    def unpack_asset(self, asset_config: AssetConfig, archive_path: Path, target_dir: Path) -> None:
        """Unpack an archived asset.

        Args:
            asset_config: The asset configuration.
            archive_path: The path to the archive file.
            target_dir: The directory to unpack the archive to.

        Raises:
            AssetUnpackError: If there is an error unpacking the asset.
            ValueError: If the format is not supported.
        """
        if not asset_config.unpack:
            logger.debug(f"Asset '{asset_config.name}' is not configured for unpacking")
            return

        if not asset_config.unpack_format:
            raise AssetConfigurationError(
                f"Asset '{asset_config.name}' is configured for unpacking but no format is specified"
            )

        # Acquire a lock on the target directory to prevent race conditions
        lock_path = self._get_lock_path_for_asset(asset_config)
        logger.info(f"Unpacking asset '{asset_config.name}' to {target_dir}")

        try:
            with asset_lock(lock_path):
                # Check if we've already unpacked
                if (target_dir / ".unpacked").exists():
                    logger.info(f"Asset '{asset_config.name}' is already unpacked")
                    return

                # Ensure the target directory exists
                target_dir.mkdir(parents=True, exist_ok=True)

                # Unpack the archive
                unpack_archive(archive_path, target_dir, asset_config.unpack_format)

                # Create a marker file to indicate successful unpacking
                (target_dir / ".unpacked").touch()

                # Optionally, delete the archive file to save space
                archive_path.unlink()

                logger.info(f"Successfully unpacked asset '{asset_config.name}'")
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
