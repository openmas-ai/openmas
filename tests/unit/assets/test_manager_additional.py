"""Additional tests for the AssetManager class to increase test coverage."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.assets.config import AssetConfig, AssetSourceConfig
from openmas.assets.exceptions import AssetConfigurationError, AssetUnpackError, AssetVerificationError
from openmas.assets.manager import AssetManager
from openmas.config import ProjectConfig


class TestAssetManagerAdditional:
    """Additional tests for the AssetManager class to increase test coverage."""

    @pytest.fixture
    def mock_project_config(self) -> ProjectConfig:
        """Create a mock project configuration for testing."""
        project_config = MagicMock(spec=ProjectConfig)
        project_config.assets = []
        project_config.settings = None
        return project_config

    @pytest.fixture
    def asset_manager(self, mock_project_config: ProjectConfig) -> AssetManager:
        """Create an AssetManager instance for testing."""
        manager = AssetManager(mock_project_config)
        return manager

    @pytest.mark.asyncio
    async def test_get_asset_path_nonexistent_asset(self, asset_manager):
        """Test get_asset_path with nonexistent asset."""
        # The asset name isn't in the manager's assets dict
        with pytest.raises(KeyError, match="Asset 'nonexistent' not found in project configuration"):
            await asset_manager.get_asset_path("nonexistent")

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    async def test_get_asset_path_metadata_mismatch(self, mock_async_lock, asset_manager, tmp_path):
        """Test get_asset_path when metadata exists but doesn't match configuration."""
        # Setup mock for async context manager
        mock_cm = AsyncMock()
        mock_async_lock.return_value = mock_cm
        mock_cm.__aenter__.return_value = None

        # Setup test data
        asset_name = "test-asset"
        asset_config = AssetConfig(
            name=asset_name,
            version="2.0",  # Newer version
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
            checksum="sha256:abcdef",
        )

        # Add asset to manager
        asset_manager.assets = {asset_name: asset_config}

        # Setup cache directory and paths
        cache_dir = tmp_path / "cache" / asset_name
        cache_dir.mkdir(parents=True)

        # Create asset file
        asset_file = cache_dir / "asset.bin"
        asset_file.write_bytes(b"asset content")

        # Create metadata with mismatched version
        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": asset_name, "version": "1.0", "source_type": "http"}, f)

        # Mock internal methods
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=cache_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=tmp_path / "locks" / asset_name),
            patch.object(asset_manager, "download_asset", new=AsyncMock(return_value=asset_file)),
            patch.object(asset_manager, "verify_asset", return_value=True),
        ):
            # Call the method
            result = await asset_manager.get_asset_path(asset_name)

            # Verify download was triggered due to metadata mismatch
            asset_manager.download_asset.assert_called_once_with(asset_config)
            assert result == asset_file

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    async def test_get_asset_path_verification_failure(self, mock_async_lock, asset_manager, tmp_path):
        """Test get_asset_path when verification fails."""
        # Setup mock for async context manager
        mock_cm = AsyncMock()
        mock_async_lock.return_value = mock_cm
        mock_cm.__aenter__.return_value = None

        # Setup test data
        asset_name = "test-asset"
        asset_config = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
            checksum="sha256:abcdef",  # Will fail verification
        )

        # Add asset to manager
        asset_manager.assets = {asset_name: asset_config}

        # Setup cache directory and paths
        cache_dir = tmp_path / "cache" / asset_name
        cache_dir.mkdir(parents=True)

        # Create asset file
        asset_file = cache_dir / "asset.bin"
        asset_file.write_bytes(b"asset content")

        # Create metadata
        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": asset_name, "version": "1.0", "source_type": "http"}, f)

        # Mock internal methods
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=cache_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=tmp_path / "locks" / asset_name),
            patch.object(asset_manager, "verify_asset", return_value=False),  # Verification fails
            patch("pathlib.Path.unlink"),  # Mock file deletion
        ):
            # Call the method - should raise verification error
            with pytest.raises(AssetVerificationError, match=f"Asset '{asset_name}' failed checksum verification"):
                await asset_manager.get_asset_path(asset_name)

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    async def test_get_asset_path_unpack_not_completed(self, mock_async_lock, asset_manager, tmp_path):
        """Test get_asset_path for asset that should be unpacked but unpacking wasn't completed."""
        # Setup mock for async context manager
        mock_cm = AsyncMock()
        mock_async_lock.return_value = mock_cm
        mock_cm.__aenter__.return_value = None

        # Setup test data
        asset_name = "test-asset"
        asset_config = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.zip"),
            unpack=True,  # Should be unpacked
            unpack_format="zip",  # Required for unpack=True
        )

        # Add asset to manager
        asset_manager.assets = {asset_name: asset_config}

        # Setup cache directory and paths
        cache_dir = tmp_path / "cache" / asset_name
        cache_dir.mkdir(parents=True)

        # Create asset file and metadata, but no unpacked marker
        asset_file = cache_dir / "asset.zip"
        asset_file.write_bytes(b"zip content")

        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": asset_name, "version": "1.0", "source_type": "http"}, f)

        # Mock internal methods
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=cache_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=tmp_path / "locks" / asset_name),
            patch.object(asset_manager, "download_asset", new=AsyncMock(return_value=asset_file)),
            patch.object(asset_manager, "unpack_asset", return_value=cache_dir),
            # Add this to prevent the mkdir error
            patch("pathlib.Path.mkdir"),
        ):
            # Call the method
            result = await asset_manager.get_asset_path(asset_name)

            # Verify download and unpack were triggered
            asset_manager.download_asset.assert_called_once_with(asset_config)
            asset_manager.unpack_asset.assert_called_once()
            assert result == cache_dir

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    async def test_get_asset_path_force_download(self, mock_async_lock, asset_manager, tmp_path):
        """Test get_asset_path with force_download=True."""
        # Setup mock for async context manager
        mock_cm = AsyncMock()
        mock_async_lock.return_value = mock_cm
        mock_cm.__aenter__.return_value = None

        # Setup test data
        asset_name = "test-asset"
        asset_config = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add asset to manager
        asset_manager.assets = {asset_name: asset_config}

        # Setup cache directory and paths
        cache_dir = tmp_path / "cache" / asset_name
        cache_dir.mkdir(parents=True)

        # Create asset file and metadata
        asset_file = cache_dir / "asset.bin"
        asset_file.write_bytes(b"asset content")

        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": asset_name, "version": "1.0", "source_type": "http"}, f)

        # Mock internal methods
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=cache_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=tmp_path / "locks" / asset_name),
            patch.object(asset_manager, "download_asset", new=AsyncMock(return_value=asset_file)),
            patch("pathlib.Path.unlink"),  # Mock file deletion
            patch("pathlib.Path.is_dir", return_value=False),
            # Add this to prevent the mkdir error
            patch("pathlib.Path.mkdir"),
        ):
            # Call the method with force_download=True
            result = await asset_manager.get_asset_path(asset_name, force_download=True)

            # Verify download was triggered despite existing file
            asset_manager.download_asset.assert_called_once_with(asset_config)
            assert result == asset_file

    def test_unpack_asset_destination_is_file(self, asset_manager, tmp_path):
        """Test unpack_asset when unpack_destination_is_file=True."""
        # Setup asset config for file extraction
        asset_config = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.zip"),
            unpack=True,
            unpack_format="zip",  # Required for unpack=True
            unpack_destination_is_file=True,  # Extract single file
        )

        # Create mock archive
        archive_path = tmp_path / "archive.zip"
        archive_path.write_bytes(b"zip content")

        target_dir = tmp_path / "extract"
        target_dir.mkdir()

        # Mock extracted file
        extracted_file = target_dir / "extracted.txt"

        # Mock unpack_archive to simulate unpacking and return single file
        with patch("openmas.assets.manager.unpack_archive") as mock_unpack:
            mock_unpack.return_value = extracted_file

            # Call the method
            result = asset_manager.unpack_asset(asset_config, archive_path, target_dir)

            # Verify result is the extracted file
            assert result == extracted_file

            # Match the actual call format with positional arguments
            mock_unpack.assert_called_once()
            args, kwargs = mock_unpack.call_args
            assert args[0] == archive_path
            assert args[1] == target_dir
            assert args[2] == "zip"
            assert kwargs["destination_is_file"] is True

    def test_unpack_asset_multiple_files_but_destination_is_file(self, asset_manager, tmp_path):
        """Test unpack_asset when unpack_destination_is_file=True but multiple files are extracted."""
        # Setup asset config for file extraction
        asset_config = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.zip"),
            unpack=True,
            unpack_format="zip",  # Required for unpack=True
            unpack_destination_is_file=True,  # Extract single file
        )

        # Create mock archive
        archive_path = tmp_path / "archive.zip"
        archive_path.write_bytes(b"zip content")

        target_dir = tmp_path / "extract"
        target_dir.mkdir()

        # Mock unpack_archive to raise an error for multiple files
        with patch("openmas.assets.manager.unpack_archive") as mock_unpack:
            mock_unpack.side_effect = AssetUnpackError("Expected a single file, but multiple files were found")

            # Call the method - should raise error for multiple files
            with pytest.raises(AssetUnpackError, match="Expected a single file"):
                asset_manager.unpack_asset(asset_config, archive_path, target_dir)

    def test_unpack_asset_no_files_extracted(self, asset_manager, tmp_path):
        """Test unpack_asset when no files are extracted."""
        # Setup asset config
        asset_config = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.zip"),
            unpack=True,
            unpack_format="zip",  # Required for unpack=True
        )

        # Create mock archive
        archive_path = tmp_path / "archive.zip"
        archive_path.write_bytes(b"zip content")

        target_dir = tmp_path / "extract"
        target_dir.mkdir()

        # Mock unpack_archive to raise an error for no files
        with patch("openmas.assets.manager.unpack_archive") as mock_unpack:
            mock_unpack.side_effect = AssetUnpackError("No files were extracted from the archive")

            # Call the method - should raise error for no files
            with pytest.raises(AssetUnpackError, match="No files were extracted"):
                asset_manager.unpack_asset(asset_config, archive_path, target_dir)

    @pytest.mark.asyncio
    async def test_download_asset_with_invalid_source_type(self, asset_manager):
        """Test download_asset with an invalid source type."""
        # Create a complete mock asset config with all required attributes
        asset_config = MagicMock()
        asset_config.name = "test-asset"
        asset_config.version = "1.0"
        asset_config.asset_type = "model"
        asset_config.source = MagicMock()
        asset_config.source.type = "invalid"
        asset_config.source.url = "https://example.com/model.bin"
        asset_config.source.filename = "model.bin"
        asset_config.checksum = None
        asset_config.retries = 0

        # We need to patch both the mkdir and cache path to avoid file system operations
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset") as mock_cache_path,
            patch("pathlib.Path.mkdir"),
        ):  # Mock the mkdir to avoid file system errors
            # Set a safe return value for the cache path
            mock_cache_path.return_value = Path("/tmp/test-asset")

            # Call the method - should raise error for invalid source type
            with pytest.raises(AssetConfigurationError, match="Unknown source type: invalid"):
                await asset_manager.download_asset(asset_config)

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    async def test_get_asset_path_unpack_exception(self, mock_async_lock, asset_manager, tmp_path):
        """Test get_asset_path when unpacking raises an exception."""
        # Setup mock for async context manager
        mock_cm = AsyncMock()
        mock_async_lock.return_value = mock_cm
        mock_cm.__aenter__.return_value = None

        # Setup test data
        asset_name = "test-asset"
        asset_config = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.zip"),
            unpack=True,  # Should be unpacked
            unpack_format="zip",  # Required for unpack=True
        )

        # Add asset to manager
        asset_manager.assets = {asset_name: asset_config}

        # Setup cache directory and paths
        cache_dir = tmp_path / "cache" / asset_name
        cache_dir.mkdir(parents=True)

        # Create asset file
        asset_file = cache_dir / "asset.zip"
        asset_file.write_bytes(b"zip content")

        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": asset_name, "version": "1.0", "source_type": "http"}, f)

        # Mock internal methods
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=cache_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=tmp_path / "locks" / asset_name),
            patch.object(asset_manager, "download_asset", new=AsyncMock(return_value=asset_file)),
            patch.object(asset_manager, "unpack_asset", side_effect=AssetUnpackError("Failed to unpack")),
            # Add this to prevent the mkdir error
            patch("pathlib.Path.mkdir"),
        ):
            # Call the method - should propagate unpack error
            with pytest.raises(AssetUnpackError, match="Failed to unpack"):
                await asset_manager.get_asset_path(asset_name)
