"""Tests for the AssetManager class."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.assets.config import AssetConfig, AssetSettings, AssetSourceConfig
from openmas.assets.exceptions import AssetConfigurationError, AssetDownloadError
from openmas.assets.manager import AssetManager
from openmas.config import ProjectConfig, SettingsConfig


class TestAssetManager:
    """Tests for the AssetManager class."""

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

    def test_init_with_default_cache_dir(self):
        """Test AssetManager initialization with default cache directory."""
        # Mock ProjectConfig with minimal assets
        project_config = MagicMock(spec=ProjectConfig)
        project_config.assets = []
        project_config.settings = None

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            # Initialize AssetManager
            manager = AssetManager(project_config)

            # Verify default cache directory is set correctly
            assert manager.cache_dir == Path.home() / ".openmas" / "assets"
            # Verify directories are created
            assert mock_mkdir.call_count == 2
            # Make sure the calls include parents=True and exist_ok=True
            mock_mkdir.assert_called_with(parents=True, exist_ok=True)

    def test_init_with_env_var_cache_dir(self):
        """Test AssetManager initialization with cache directory from environment variable."""
        # Mock ProjectConfig and environment variable
        project_config = MagicMock(spec=ProjectConfig)
        project_config.assets = []
        project_config.settings = None

        custom_cache_dir = Path("/custom/cache/dir")

        with patch.dict(os.environ, {"OPENMAS_ASSETS_DIR": str(custom_cache_dir)}), patch("pathlib.Path.mkdir"):
            # Initialize AssetManager
            manager = AssetManager(project_config)

            # Verify cache directory is set from environment variable
            assert manager.cache_dir == custom_cache_dir

    def test_init_with_project_settings_cache_dir(self):
        """Test AssetManager initialization with cache directory from project settings."""
        # Mock ProjectConfig with custom cache directory in settings
        project_config = MagicMock(spec=ProjectConfig)
        project_config.assets = []

        settings = MagicMock(spec=SettingsConfig)
        assets_settings = MagicMock(spec=AssetSettings)
        assets_settings.cache_dir = Path("/project/settings/cache/dir")
        settings.assets = assets_settings
        project_config.settings = settings

        with patch("pathlib.Path.mkdir"), patch.dict(os.environ, {}, clear=True):
            # Initialize AssetManager
            manager = AssetManager(project_config)

            # Verify cache directory is set from project settings
            assert manager.cache_dir == Path("/project/settings/cache/dir")

    def test_init_with_assets(self):
        """Test AssetManager initialization with assets."""
        # Create mock assets
        asset1 = AssetConfig(
            name="asset1",
            source=AssetSourceConfig(type="http", url="https://example.com/asset1.bin"),
        )
        asset2 = AssetConfig(
            name="asset2",
            source=AssetSourceConfig(type="hf", repo_id="example/asset2"),
        )

        # Mock ProjectConfig with assets
        project_config = MagicMock(spec=ProjectConfig)
        project_config.assets = [asset1, asset2]
        project_config.settings = None

        with patch("pathlib.Path.mkdir"):
            # Initialize AssetManager
            manager = AssetManager(project_config)

            # Verify assets are stored correctly
            assert len(manager.assets) == 2
            assert manager.assets["asset1"] == asset1
            assert manager.assets["asset2"] == asset2

    def test_check_asset_status_not_cached(self, asset_manager, tmp_path):
        """Test check_asset_status when the asset is not cached."""
        # Set up a mock cache path
        with patch.object(asset_manager, "_get_cache_path_for_asset") as mock_get_cache_path:
            mock_get_cache_path.return_value = tmp_path / "cache" / "asset"

            # Create an asset config
            asset_config = AssetConfig(
                name="test-asset",
                version="1.0",
                source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
            )

            # Check the status
            status = asset_manager.check_asset_status(asset_config)

            # Verify the result
            assert status["exists"] is False
            assert status["verified"] is False
            assert status["path"] is None

    def test_check_asset_status_cached_with_no_checksum(self, asset_manager, tmp_path):
        """Test check_asset_status when the asset is cached but has no checksum."""
        # Set up a mock cache path
        cache_dir = tmp_path / "cache" / "asset"
        cache_dir.mkdir(parents=True)

        # Create a file and metadata
        filename = "asset.bin"
        file_path = cache_dir / filename
        file_path.write_bytes(b"asset content")

        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": "test-asset", "version": "1.0"}, f)

        with patch.object(asset_manager, "_get_cache_path_for_asset") as mock_get_cache_path:
            mock_get_cache_path.return_value = cache_dir

            # Create an asset config (no checksum)
            asset_config = AssetConfig(
                name="test-asset",
                version="1.0",
                source=AssetSourceConfig(type="http", url="https://example.com/asset.bin", filename="asset.bin"),
            )

            # Check the status
            status = asset_manager.check_asset_status(asset_config)

            # Verify the result
            assert status["exists"] is True
            assert status["verified"] is True  # No checksum, so considered verified
            assert status["path"] == file_path

    def test_check_asset_status_cached_with_checksum_verified(self, asset_manager, tmp_path):
        """Test check_asset_status when the asset is cached and verifies with checksum."""
        # Set up a mock cache path
        cache_dir = tmp_path / "cache" / "asset"
        cache_dir.mkdir(parents=True)

        # Create a file and metadata
        filename = "asset.bin"
        file_path = cache_dir / filename
        file_path.write_bytes(b"asset content")

        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": "test-asset", "version": "1.0"}, f)

        with (
            patch.object(asset_manager, "_get_cache_path_for_asset") as mock_get_cache_path,
            patch.object(asset_manager, "verify_asset", return_value=True) as mock_verify_asset,
        ):
            mock_get_cache_path.return_value = cache_dir

            # Create an asset config with checksum
            asset_config = AssetConfig(
                name="test-asset",
                version="1.0",
                source=AssetSourceConfig(type="http", url="https://example.com/asset.bin", filename="asset.bin"),
                checksum="sha256:abcdef",
            )

            # Check the status
            status = asset_manager.check_asset_status(asset_config)

            # Verify the result
            assert status["exists"] is True
            assert status["verified"] is True
            assert status["path"] == file_path
            mock_verify_asset.assert_called_once_with(asset_config, file_path)

    def test_check_asset_status_cached_with_checksum_failed(self, asset_manager, tmp_path):
        """Test check_asset_status when the asset is cached but checksum verification fails."""
        # Set up a mock cache path
        cache_dir = tmp_path / "cache" / "asset"
        cache_dir.mkdir(parents=True)

        # Create a file and metadata
        filename = "asset.bin"
        file_path = cache_dir / filename
        file_path.write_bytes(b"asset content")

        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": "test-asset", "version": "1.0"}, f)

        with (
            patch.object(asset_manager, "_get_cache_path_for_asset") as mock_get_cache_path,
            patch.object(asset_manager, "verify_asset", return_value=False) as mock_verify_asset,
        ):
            mock_get_cache_path.return_value = cache_dir

            # Create an asset config with checksum
            asset_config = AssetConfig(
                name="test-asset",
                version="1.0",
                source=AssetSourceConfig(type="http", url="https://example.com/asset.bin", filename="asset.bin"),
                checksum="sha256:abcdef",
            )

            # Check the status
            status = asset_manager.check_asset_status(asset_config)

            # Verify the result
            assert status["exists"] is True
            assert status["verified"] is False
            assert status["path"] == file_path
            mock_verify_asset.assert_called_once_with(asset_config, file_path)

    def test_check_asset_status_with_unpacked_asset(self, asset_manager, tmp_path):
        """Test check_asset_status with an unpacked asset."""
        # Set up a mock cache path
        cache_dir = tmp_path / "cache" / "asset"
        cache_dir.mkdir(parents=True)

        # Create the unpacked directory structure
        unpacked_dir = cache_dir
        (unpacked_dir / "file1.txt").write_text("content1")
        (unpacked_dir / "file2.txt").write_text("content2")

        metadata_path = cache_dir / ".asset_info.json"
        with open(metadata_path, "w") as f:
            json.dump({"name": "test-asset", "version": "1.0"}, f)

        with patch.object(asset_manager, "_get_cache_path_for_asset") as mock_get_cache_path:
            mock_get_cache_path.return_value = cache_dir

            # Create an asset config for unpacked archive
            asset_config = AssetConfig(
                name="test-asset",
                version="1.0",
                source=AssetSourceConfig(type="http", url="https://example.com/archive.zip"),
                unpack=True,
                unpack_format="zip",
            )

            # Check the status
            status = asset_manager.check_asset_status(asset_config)

            # Verify the result
            assert status["exists"] is True
            assert status["verified"] is True  # No checksum, so considered verified
            assert status["path"] == unpacked_dir

    def test_get_cache_path_for_asset(self):
        """Test the _get_cache_path_for_asset method."""
        # Mock ProjectConfig
        project_config = MagicMock(spec=ProjectConfig)
        project_config.assets = []
        project_config.settings = None

        with patch("pathlib.Path.mkdir"):
            # Initialize AssetManager
            manager = AssetManager(project_config)

            # Create test asset config
            asset_config = AssetConfig(
                name="test-model",
                version="1.0.0",
                asset_type="model",
                source=AssetSourceConfig(type="http", url="https://example.com/model.bin"),
            )

            # Get cache path
            cache_path = manager._get_cache_path_for_asset(asset_config)

            # Verify path follows expected structure
            expected_path = manager.cache_dir / "model" / "test-model" / "1.0.0"
            assert cache_path == expected_path

    def test_get_lock_path_for_asset(self):
        """Test the _get_lock_path_for_asset method."""
        # Mock ProjectConfig
        project_config = MagicMock(spec=ProjectConfig)
        project_config.assets = []
        project_config.settings = None

        with patch("pathlib.Path.mkdir"):
            # Initialize AssetManager
            manager = AssetManager(project_config)

            # Create test asset config
            asset_config = AssetConfig(
                name="test-model",
                version="1.0.0",
                asset_type="model",
                source=AssetSourceConfig(type="http", url="https://example.com/model.bin"),
            )

            # Get lock path
            lock_path = manager._get_lock_path_for_asset(asset_config)

            # Verify path follows expected structure
            expected_path = manager.locks_dir / "test-model_1.0.0.lock"
            assert lock_path == expected_path

    @pytest.mark.asyncio
    async def test_download_asset_with_http_source(self, asset_manager: AssetManager) -> None:
        """Test downloading an asset with HTTP source."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Mock the get_downloader_for_source function
        mock_downloader = AsyncMock()
        with patch(
            "openmas.assets.manager.get_downloader_for_source", return_value=mock_downloader
        ) as mock_get_downloader:
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset
                result = await asset_manager.download_asset(asset)

                # Check that the downloader was called with the correct arguments
                mock_get_downloader.assert_called_once_with(asset.source)
                mock_downloader.download.assert_called_once()

                # Check the source config was passed correctly
                call_args = mock_downloader.download.call_args[0]
                assert call_args[0] == asset.source

                # Check the target path
                expected_path = asset_manager._get_cache_path_for_asset(asset) / "asset.bin"
                assert call_args[1] == expected_path

                # Check the return value
                assert result == expected_path

    @pytest.mark.asyncio
    async def test_download_asset_with_hf_source(self, asset_manager: AssetManager) -> None:
        """Test downloading an asset with Hugging Face source."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="hf", repo_id="test/model", filename="model.bin"),
        )

        # Mock the get_downloader_for_source function
        mock_downloader = AsyncMock()
        with patch(
            "openmas.assets.manager.get_downloader_for_source", return_value=mock_downloader
        ) as mock_get_downloader:
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset
                result = await asset_manager.download_asset(asset)

                # Check that the downloader was called with the correct arguments
                mock_get_downloader.assert_called_once_with(asset.source)
                mock_downloader.download.assert_called_once()

                # Check the source config was passed correctly
                call_args = mock_downloader.download.call_args[0]
                assert call_args[0] == asset.source

                # Check the target path
                expected_path = asset_manager._get_cache_path_for_asset(asset) / "model.bin"
                assert call_args[1] == expected_path

                # Check the return value
                assert result == expected_path

    @pytest.mark.asyncio
    async def test_download_asset_with_local_source(self, asset_manager: AssetManager) -> None:
        """Test downloading an asset with local source."""
        # Create mock asset with local source
        source_path = Path("/path/to/local/asset.bin")
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="local", path=source_path),
        )

        # Mock the get_downloader_for_source function
        mock_downloader = AsyncMock()

        with patch(
            "openmas.assets.manager.get_downloader_for_source", return_value=mock_downloader
        ) as mock_get_downloader:
            # Create a mock for the expected file path
            expected_path = asset_manager._get_cache_path_for_asset(asset) / "asset"

            # Set up the mock to return our expected path
            mock_downloader.download.return_value = expected_path

            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset
                result = await asset_manager.download_asset(asset)

                # Check that the downloader was called with the correct arguments
                mock_get_downloader.assert_called_once_with(asset.source)
                mock_downloader.download.assert_called_once()

                # Check the source config was passed correctly
                call_args = mock_downloader.download.call_args[0]
                assert call_args[0] == asset.source

                # Check the target path
                assert call_args[1] == expected_path

                # Check the return value
                assert result == expected_path

    @pytest.mark.asyncio
    async def test_download_asset_with_download_error(self, asset_manager: AssetManager) -> None:
        """Test handling of AssetDownloadError during download."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Mock the get_downloader_for_source function to raise AssetDownloadError
        mock_downloader = AsyncMock()
        mock_downloader.download.side_effect = AssetDownloadError("Download failed")
        with patch(
            "openmas.assets.manager.get_downloader_for_source", return_value=mock_downloader
        ) as mock_get_downloader:
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset and expect the error to be re-raised
                with pytest.raises(AssetDownloadError, match="Download failed"):
                    await asset_manager.download_asset(asset)

                # Check that the downloader was called with the correct arguments
                mock_get_downloader.assert_called_once_with(asset.source)
                mock_downloader.download.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_asset_with_config_error(self, asset_manager: AssetManager) -> None:
        """Test handling of AssetConfigurationError during downloader setup."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Mock the get_downloader_for_source function to raise AssetConfigurationError
        with patch(
            "openmas.assets.manager.get_downloader_for_source",
            side_effect=AssetConfigurationError("Invalid configuration"),
        ) as mock_get_downloader:
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset and expect the error to be re-raised
                with pytest.raises(AssetConfigurationError, match="Invalid configuration"):
                    await asset_manager.download_asset(asset)

                # Check that the downloader was called with the correct arguments
                mock_get_downloader.assert_called_once_with(asset.source)

    @pytest.mark.asyncio
    async def test_download_asset_with_unexpected_error(self, asset_manager: AssetManager) -> None:
        """Test handling of unexpected errors during download."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Mock the get_downloader_for_source function to raise RuntimeError
        with patch(
            "openmas.assets.manager.get_downloader_for_source",
            side_effect=RuntimeError("Unexpected error"),
        ) as mock_get_downloader:
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset and expect the error to be wrapped as AssetDownloadError
                with pytest.raises(AssetDownloadError) as excinfo:
                    await asset_manager.download_asset(asset)

                # Check that the error message contains the expected information
                error_msg = str(excinfo.value)
                assert "Unexpected error downloading asset" in error_msg
                assert "test-asset" in error_msg
                assert "Unexpected error" in error_msg

                # Verify the mock was called
                mock_get_downloader.assert_called_once_with(asset.source)


class TestAssetManagerClearCache:
    """Tests for the cache clearing methods of AssetManager."""

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

    def test_clear_asset_cache_success(self, asset_manager, tmp_path):
        """Test clearing the cache for a specific asset successfully."""
        # Set up asset_manager and asset
        asset_name = "test-asset"

        # Create a mock asset
        asset = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add asset to manager's asset dictionary
        asset_manager.assets[asset_name] = asset

        # Create a mock asset directory
        asset_dir = tmp_path / "asset-cache"
        asset_dir.mkdir()
        (asset_dir / "test-file.bin").write_bytes(b"test data")

        with patch.object(asset_manager, "_get_cache_path_for_asset", return_value=asset_dir) as mock_get_cache_path:
            # Call clear_asset_cache
            result = asset_manager.clear_asset_cache(asset_name)

            # Verify the result
            assert result is True
            mock_get_cache_path.assert_called_once_with(asset)

            # Verify the directory was removed
            assert not asset_dir.exists()

    def test_clear_asset_cache_nonexistent_asset(self, asset_manager):
        """Test clearing the cache for a nonexistent asset."""
        # Call clear_asset_cache with a nonexistent asset name
        with pytest.raises(KeyError, match="Asset 'nonexistent' not found"):
            asset_manager.clear_asset_cache("nonexistent")

    def test_clear_asset_cache_nonexistent_directory(self, asset_manager, tmp_path):
        """Test clearing the cache for an asset whose directory doesn't exist."""
        # Set up asset_manager and asset
        asset_name = "test-asset"

        # Create a mock asset
        asset = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add asset to manager's asset dictionary
        asset_manager.assets[asset_name] = asset

        # Return a nonexistent directory
        nonexistent_dir = tmp_path / "nonexistent"

        with patch.object(
            asset_manager, "_get_cache_path_for_asset", return_value=nonexistent_dir
        ) as mock_get_cache_path:
            # Call clear_asset_cache
            result = asset_manager.clear_asset_cache(asset_name)

            # Verify the result (should still return True)
            assert result is True
            mock_get_cache_path.assert_called_once_with(asset)

    def test_clear_asset_cache_exception(self, asset_manager, tmp_path):
        """Test handling exceptions when clearing the cache for an asset."""
        # Set up asset_manager and asset
        asset_name = "test-asset"

        # Create a mock asset
        asset = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add asset to manager's asset dictionary
        asset_manager.assets[asset_name] = asset

        # Create a mock asset directory
        asset_dir = tmp_path / "asset-cache"
        asset_dir.mkdir()

        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=asset_dir) as mock_get_cache_path,
            patch("shutil.rmtree", side_effect=PermissionError("Permission denied")) as mock_rmtree,
        ):
            # Call clear_asset_cache
            result = asset_manager.clear_asset_cache(asset_name)

            # Verify the result
            assert result is False
            mock_get_cache_path.assert_called_once_with(asset)
            mock_rmtree.assert_called_once_with(asset_dir)

    def test_clear_entire_cache_success(self, asset_manager, tmp_path):
        """Test clearing the entire cache successfully."""
        # Set the cache directory
        asset_manager.cache_dir = tmp_path / "cache"
        asset_manager.cache_dir.mkdir()

        # Create some test directories in the cache
        (asset_manager.cache_dir / "dir1").mkdir()
        (asset_manager.cache_dir / "dir2").mkdir()
        (asset_manager.cache_dir / ".locks").mkdir()  # Should be preserved

        # Create an HF cache directory (should be preserved by default)
        hf_cache = asset_manager.cache_dir / "huggingface"
        hf_cache.mkdir()

        # Call clear_entire_cache
        asset_manager.clear_entire_cache()

        # Verify the directories were removed except for .locks and huggingface
        assert not (asset_manager.cache_dir / "dir1").exists()
        assert not (asset_manager.cache_dir / "dir2").exists()
        assert (asset_manager.cache_dir / ".locks").exists()
        assert (asset_manager.cache_dir / "huggingface").exists()

        # Verify the cache directory itself still exists
        assert asset_manager.cache_dir.exists()

    def test_clear_entire_cache_include_hf(self, asset_manager, tmp_path):
        """Test clearing the entire cache including Hugging Face cache."""
        # Set the cache directory
        asset_manager.cache_dir = tmp_path / "cache"
        asset_manager.cache_dir.mkdir()

        # Create some test directories in the cache
        (asset_manager.cache_dir / "dir1").mkdir()
        (asset_manager.cache_dir / ".locks").mkdir()  # Should be preserved

        # Create an HF cache directory
        hf_cache = asset_manager.cache_dir / "huggingface"
        hf_cache.mkdir()

        # Call clear_entire_cache with exclude_hf_cache=False
        asset_manager.clear_entire_cache(exclude_hf_cache=False)

        # Verify the directories were removed except for .locks
        assert not (asset_manager.cache_dir / "dir1").exists()
        assert (asset_manager.cache_dir / ".locks").exists()
        assert not (asset_manager.cache_dir / "huggingface").exists()

    def test_clear_entire_cache_empty(self, asset_manager, tmp_path):
        """Test clearing an empty cache."""
        # Set the cache directory
        asset_manager.cache_dir = tmp_path / "cache"
        asset_manager.cache_dir.mkdir()

        # Create only .locks directory
        (asset_manager.cache_dir / ".locks").mkdir()

        # Call clear_entire_cache
        asset_manager.clear_entire_cache()

        # Verify .locks directory still exists
        assert (asset_manager.cache_dir / ".locks").exists()

        # Verify the cache directory itself still exists
        assert asset_manager.cache_dir.exists()

    def test_clear_entire_cache_exception(self, asset_manager, tmp_path):
        """Test handling exceptions when clearing the entire cache."""
        # Set the cache directory
        asset_manager.cache_dir = tmp_path / "cache"
        asset_manager.cache_dir.mkdir()

        # Create a test directory
        test_dir = asset_manager.cache_dir / "test"
        test_dir.mkdir()

        with patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            # Call clear_entire_cache
            # Should not raise an exception
            asset_manager.clear_entire_cache()

            # Since rmtree failed, the directory should still exist
            assert test_dir.exists()


class TestAssetManagerGetAssetPathRetries:
    """Tests for the get_asset_path method of AssetManager with retries."""

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
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_with_retries_success(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test get_asset_path with retries eventually succeeding."""
        # Set up asset and manager
        asset_name = "test-asset"
        asset_dir = tmp_path / "asset-dir"
        asset_dir.mkdir(parents=True)
        downloaded_file = asset_dir / "asset.bin"

        # Create an asset with multiple retries
        asset = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
            retries=2,  # Will try up to 3 times (initial + 2 retries)
        )

        # Add to manager's assets
        asset_manager.assets[asset_name] = asset

        # Mock async_asset_lock to pass through the context
        mock_context = MagicMock()
        mock_async_lock_instance = AsyncMock()
        mock_async_lock_instance.__aenter__.return_value = mock_context
        mock_async_asset_lock.return_value = mock_async_lock_instance

        # Mock _get_cache_path_for_asset and _get_lock_path_for_asset
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=asset_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=Path("lock_path")),
        ):
            # Mock the download_asset method to fail twice then succeed
            mock_download_asset.side_effect = [
                AssetDownloadError("Download failed (attempt 1)"),
                AssetDownloadError("Download failed (attempt 2)"),
                downloaded_file,  # Success on third attempt
            ]

            # Call get_asset_path
            result = await asset_manager.get_asset_path(asset_name)

            # Verify the result
            assert result == downloaded_file

            # Verify download_asset was called 3 times
            assert mock_download_asset.call_count == 3

            # Verify metadata was created
            metadata_path = asset_dir / ".asset_info.json"
            assert metadata_path.exists()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_with_retries_exhausted(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test get_asset_path with retries exhausted."""
        # Set up asset and manager
        asset_name = "test-asset"
        asset_dir = tmp_path / "asset-dir"
        asset_dir.mkdir(parents=True)

        # Create an asset with multiple retries
        asset = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
            retries=1,  # Will try up to 2 times (initial + 1 retry)
        )

        # Add to manager's assets
        asset_manager.assets[asset_name] = asset

        # Mock async_asset_lock to pass through the context
        mock_context = MagicMock()
        mock_async_lock_instance = AsyncMock()
        mock_async_lock_instance.__aenter__.return_value = mock_context
        mock_async_asset_lock.return_value = mock_async_lock_instance

        # Mock _get_cache_path_for_asset and _get_lock_path_for_asset
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=asset_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=Path("lock_path")),
        ):
            # Mock the download_asset method to fail every time
            mock_download_asset.side_effect = AssetDownloadError("Download failed repeatedly")

            # Call get_asset_path and expect an error
            with pytest.raises(AssetDownloadError, match="Failed to download asset"):
                await asset_manager.get_asset_path(asset_name)

            # Verify download_asset was called 2 times
            assert mock_download_asset.call_count == 2

            # Verify no metadata was created
            metadata_path = asset_dir / ".asset_info.json"
            assert not metadata_path.exists()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_with_different_errors(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test get_asset_path with different types of errors during retries."""
        # Set up asset and manager
        asset_name = "test-asset"
        asset_dir = tmp_path / "asset-dir"
        asset_dir.mkdir(parents=True)
        downloaded_file = asset_dir / "asset.bin"

        # Create an asset with multiple retries
        asset = AssetConfig(
            name=asset_name,
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
            retries=2,  # Will try up to 3 times (initial + 2 retries)
        )

        # Add to manager's assets
        asset_manager.assets[asset_name] = asset

        # Mock async_asset_lock to pass through the context
        mock_context = MagicMock()
        mock_async_lock_instance = AsyncMock()
        mock_async_lock_instance.__aenter__.return_value = mock_context
        mock_async_asset_lock.return_value = mock_async_lock_instance

        # Mock _get_cache_path_for_asset and _get_lock_path_for_asset
        with (
            patch.object(asset_manager, "_get_cache_path_for_asset", return_value=asset_dir),
            patch.object(asset_manager, "_get_lock_path_for_asset", return_value=Path("lock_path")),
            patch.object(
                asset_manager,
                "download_asset",
                side_effect=[
                    AssetDownloadError("Network error"),
                    AssetDownloadError("Connection failed"),  # Wrap in AssetDownloadError
                    downloaded_file,  # Success on third attempt
                ],
            ),
        ):
            # Call get_asset_path
            result = await asset_manager.get_asset_path(asset_name)

            # Verify the result
            assert result == downloaded_file

            # Verify download_asset was called 3 times
            assert asset_manager.download_asset.call_count == 3
