"""Tests for the AssetManager class."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.assets.config import AssetConfig, AssetSettings, AssetSourceConfig
from openmas.assets.exceptions import AssetConfigurationError, AssetDownloadError, AssetVerificationError
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
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset
                result = await asset_manager.download_asset(asset)

                # Check that the downloader was called with the correct arguments
                mock_get_downloader.assert_called_once_with(asset.source)
                mock_downloader.download.assert_called_once()

                # Check the target path (should use "asset" as default filename)
                expected_path = asset_manager._get_cache_path_for_asset(asset) / "asset"
                assert mock_downloader.download.call_args[0][1] == expected_path

                # Check the return value
                assert result == expected_path

    @pytest.mark.asyncio
    async def test_download_asset_with_download_error(self, asset_manager: AssetManager) -> None:
        """Test downloading an asset with a download error."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Mock the get_downloader_for_source function to raise a download error
        mock_downloader = AsyncMock()
        mock_downloader.download.side_effect = AssetDownloadError(
            "Download failed", source_type="http", source_info="https://example.com/asset.bin"
        )

        with patch("openmas.assets.manager.get_downloader_for_source", return_value=mock_downloader):
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset and expect an error
                with pytest.raises(AssetDownloadError) as exc_info:
                    await asset_manager.download_asset(asset)

                # Check the error message
                assert "Download failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_asset_with_config_error(self, asset_manager: AssetManager) -> None:
        """Test downloading an asset with a configuration error."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Mock the get_downloader_for_source function to raise a configuration error
        with patch(
            "openmas.assets.manager.get_downloader_for_source",
            side_effect=AssetConfigurationError("Invalid configuration"),
        ):
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset and expect an error
                with pytest.raises(AssetConfigurationError) as exc_info:
                    await asset_manager.download_asset(asset)

                # Check the error message
                assert "Invalid configuration" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_asset_with_unexpected_error(self, asset_manager: AssetManager) -> None:
        """Test downloading an asset with an unexpected error."""
        # Create mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Mock the get_downloader_for_source function to raise an unexpected error
        with patch("openmas.assets.manager.get_downloader_for_source", side_effect=RuntimeError("Unexpected error")):
            # Mock the mkdir method to avoid filesystem operations
            with patch("pathlib.Path.mkdir"):
                # Call download_asset and expect an error
                with pytest.raises(AssetDownloadError) as exc_info:
                    await asset_manager.download_asset(asset)

                # Check the error message
                assert "Unexpected error downloading asset 'test-asset'" in str(exc_info.value)
                assert "Unexpected error" in str(exc_info.value)


@pytest.fixture
def mock_project_config():
    """Create a mock ProjectConfig with assets."""
    # Create a simple asset configuration
    assets = [
        AssetConfig(
            name="test-model",
            version="1.0",
            asset_type="model",
            source=AssetSourceConfig(type="http", url="https://example.com/model.bin"),
        ),
        AssetConfig(
            name="test-archive",
            version="1.0",
            asset_type="dataset",
            source=AssetSourceConfig(type="http", url="https://example.com/data.zip"),
            unpack=True,
            unpack_format="zip",
        ),
        AssetConfig(
            name="test-with-checksum",
            version="1.0",
            asset_type="model",
            source=AssetSourceConfig(type="http", url="https://example.com/with-checksum.bin"),
            checksum="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
    ]

    # Create a mock ProjectConfig
    project_config = MagicMock(spec=ProjectConfig)
    project_config.assets = assets

    # Create mock settings
    settings = MagicMock()
    settings.assets = AssetSettings(cache_dir=None)
    project_config.settings = settings

    return project_config


@pytest.fixture
def asset_manager(mock_project_config, tmp_path):
    """Create an AssetManager with a temporary cache directory."""
    # Override the cache directory to use a temporary path
    os.environ["OPENMAS_ASSETS_DIR"] = str(tmp_path)

    # Create the AssetManager
    manager = AssetManager(mock_project_config)

    # Yield the manager for the test
    yield manager

    # Clean up
    if "OPENMAS_ASSETS_DIR" in os.environ:
        del os.environ["OPENMAS_ASSETS_DIR"]


class TestAssetManagerVerify:
    """Tests for AssetManager.verify_asset method."""

    def test_verify_asset_no_checksum(self, asset_manager, tmp_path):
        """Test verify_asset when no checksum is specified."""
        # Create a mock asset config without a checksum
        asset_config = AssetConfig(
            name="test",
            source=AssetSourceConfig(type="http", url="https://example.com/test.bin"),
        )

        # Create a dummy file
        asset_path = tmp_path / "test.bin"
        asset_path.touch()

        # Verify should return True (skipped)
        assert asset_manager.verify_asset(asset_config, asset_path) is True

    @patch("openmas.assets.manager.verify_checksum")
    def test_verify_asset_with_checksum_success(self, mock_verify_checksum, asset_manager, tmp_path):
        """Test verify_asset with a valid checksum."""
        # Create a mock asset config with a checksum
        asset_config = AssetConfig(
            name="test",
            source=AssetSourceConfig(type="http", url="https://example.com/test.bin"),
            checksum="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )

        # Create a dummy file
        asset_path = tmp_path / "test.bin"
        asset_path.touch()

        # Configure the mock to return True
        mock_verify_checksum.return_value = True

        # Verify should return True
        assert asset_manager.verify_asset(asset_config, asset_path) is True

        # Verify the mock was called correctly
        mock_verify_checksum.assert_called_once_with(
            asset_path,
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )

    @patch("openmas.assets.manager.verify_checksum")
    def test_verify_asset_with_checksum_failure(self, mock_verify_checksum, asset_manager, tmp_path):
        """Test verify_asset with an invalid checksum."""
        # Create a mock asset config with a checksum
        asset_config = AssetConfig(
            name="test",
            source=AssetSourceConfig(type="http", url="https://example.com/test.bin"),
            checksum="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )

        # Create a dummy file
        asset_path = tmp_path / "test.bin"
        asset_path.touch()

        # Configure the mock to return False
        mock_verify_checksum.return_value = False

        # Verify should return False
        assert asset_manager.verify_asset(asset_config, asset_path) is False

        # Verify the mock was called correctly
        mock_verify_checksum.assert_called_once_with(
            asset_path,
            "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )


class TestAssetManagerUnpack:
    """Tests for AssetManager.unpack_asset method."""

    def test_unpack_asset_not_configured(self, asset_manager, tmp_path):
        """Test unpack_asset when unpacking is not configured."""
        # Create a mock asset config without unpack
        asset_config = AssetConfig(
            name="test",
            source=AssetSourceConfig(type="http", url="https://example.com/test.bin"),
        )

        # Create dummy files
        archive_path = tmp_path / "test.bin"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Should not raise any exceptions
        asset_manager.unpack_asset(asset_config, archive_path, target_dir)

        # The target directory should still be empty
        assert list(target_dir.iterdir()) == []

    def test_unpack_asset_missing_format(self, asset_manager, tmp_path):
        """Test unpack_asset when unpack is True but format is missing."""
        # Create a mock asset config with unpack but no format using MagicMock to bypass validation
        asset_config = MagicMock(spec=AssetConfig)
        asset_config.name = "test"
        asset_config.source = AssetSourceConfig(type="http", url="https://example.com/test.zip")
        asset_config.unpack = True
        asset_config.unpack_format = None

        # Create dummy files
        archive_path = tmp_path / "test.zip"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Should raise an exception
        with pytest.raises(AssetConfigurationError):
            asset_manager.unpack_asset(asset_config, archive_path, target_dir)

    @patch("openmas.assets.manager.unpack_archive")
    @patch("openmas.assets.manager.asset_lock")
    def test_unpack_asset_success(self, mock_asset_lock, mock_unpack_archive, asset_manager, tmp_path):
        """Test successful unpacking of an asset."""
        # Create a mock asset config
        asset_config = AssetConfig(
            name="test",
            source=AssetSourceConfig(type="http", url="https://example.com/test.zip"),
            unpack=True,
            unpack_format="zip",
        )

        # Create dummy files
        archive_path = tmp_path / "test.zip"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Configure the mock context manager
        mock_asset_lock.return_value.__enter__.return_value = None

        # Call the method
        asset_manager.unpack_asset(asset_config, archive_path, target_dir)

        # Verify the mocks were called correctly
        mock_asset_lock.assert_called_once()
        mock_unpack_archive.assert_called_once_with(archive_path, target_dir, "zip")

        # Verify the marker file was created
        assert (target_dir / ".unpacked").exists()

    @patch("openmas.assets.manager.unpack_archive")
    @patch("openmas.assets.manager.asset_lock")
    def test_unpack_asset_already_unpacked(self, mock_asset_lock, mock_unpack_archive, asset_manager, tmp_path):
        """Test unpacking when the asset is already unpacked."""
        # Create a mock asset config
        asset_config = AssetConfig(
            name="test",
            source=AssetSourceConfig(type="http", url="https://example.com/test.zip"),
            unpack=True,
            unpack_format="zip",
        )

        # Create dummy files
        archive_path = tmp_path / "test.zip"
        archive_path.touch()
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create the marker file to indicate it's already unpacked
        (target_dir / ".unpacked").touch()

        # Configure the mock context manager
        mock_asset_lock.return_value.__enter__.return_value = None

        # Call the method
        asset_manager.unpack_asset(asset_config, archive_path, target_dir)

        # Verify the lock was acquired
        mock_asset_lock.assert_called_once()

        # Verify unpack_archive was NOT called
        mock_unpack_archive.assert_not_called()


class TestAssetManagerGetAssetPath:
    """Tests for AssetManager.get_asset_path method."""

    @pytest.mark.asyncio
    async def test_get_asset_path_nonexistent_asset(self, asset_manager):
        """Test get_asset_path with a nonexistent asset name."""
        with pytest.raises(KeyError):
            await asset_manager.get_asset_path("nonexistent-asset")

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    async def test_get_asset_path_already_cached(self, mock_async_asset_lock, asset_manager, tmp_path):
        """Test get_asset_path when the asset is already cached."""
        # Configure the mock async context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None
        mock_async_asset_lock.return_value.__aexit__.return_value = None

        # Create a mock asset config
        asset_config = AssetConfig(
            name="test-model",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/model.bin"),
        )
        # Add it to the manager's assets dictionary
        asset_manager.assets = {"test-model": asset_config}

        # Create the cached asset
        asset_dir = tmp_path / "model" / "test-model" / "1.0"
        asset_dir.mkdir(parents=True)
        asset_file = asset_dir / "model.bin"
        asset_file.touch()

        # Create metadata file
        metadata_path = asset_dir / ".asset_info.json"
        metadata = {
            "name": "test-model",
            "version": "1.0",
            "asset_type": "model",
            "source_type": "http",
            "checksum": None,
            "unpack": False,
            "unpack_format": None,
            "description": None,
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        # Mock get_cache_path_for_asset to return our test path
        asset_manager._get_cache_path_for_asset = MagicMock(return_value=asset_dir)

        # Get the asset path
        result = await asset_manager.get_asset_path("test-model")

        # Verify the result
        assert result == asset_file

        # Verify the lock was acquired
        mock_async_asset_lock.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_download_needed(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test get_asset_path when the asset needs to be downloaded."""
        # Configure the mock async context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None

        # Configure the download mock
        downloaded_path = tmp_path / "model" / "test-model" / "1.0" / "model.bin"
        mock_download_asset.return_value = downloaded_path

        # Get the asset path
        result = await asset_manager.get_asset_path("test-model")

        # Verify the result
        assert result == downloaded_path

        # Verify the download was called
        mock_download_asset.assert_called_once()

        # Verify the lock was acquired
        mock_async_asset_lock.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    @patch("openmas.assets.manager.AssetManager.verify_asset")
    async def test_get_asset_path_with_checksum(
        self, mock_verify_asset, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test get_asset_path with an asset that has a checksum."""
        # Configure the mock async context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None

        # Configure the download mock
        downloaded_path = tmp_path / "model" / "test-with-checksum" / "1.0" / "with-checksum.bin"
        mock_download_asset.return_value = downloaded_path

        # Configure the verify mock
        mock_verify_asset.return_value = True

        # Get the asset path
        result = await asset_manager.get_asset_path("test-with-checksum")

        # Verify the result
        assert result == downloaded_path

        # Verify the download was called
        mock_download_asset.assert_called_once()

        # Verify the verify was called
        mock_verify_asset.assert_called_once()

        # Verify the lock was acquired
        mock_async_asset_lock.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    @patch("openmas.assets.manager.AssetManager.verify_asset")
    async def test_get_asset_path_checksum_failure(
        self, mock_verify_asset, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test get_asset_path when checksum verification fails."""
        # Configure the mock async context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None

        # Configure the download mock
        downloaded_path = tmp_path / "model" / "test-with-checksum" / "1.0" / "with-checksum.bin"
        mock_download_asset.return_value = downloaded_path

        # Configure the verify mock to fail
        mock_verify_asset.return_value = False

        # Should raise an exception
        with pytest.raises(AssetVerificationError):
            await asset_manager.get_asset_path("test-with-checksum")

        # Verify the download was called
        mock_download_asset.assert_called_once()

        # Verify the verify was called
        mock_verify_asset.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    @patch("openmas.assets.manager.AssetManager.unpack_asset")
    async def test_get_asset_path_with_unpacking(
        self, mock_unpack_asset, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test get_asset_path with an asset that needs unpacking."""
        # Configure the mock async context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None

        # Configure the download mock
        downloaded_path = tmp_path / "dataset" / "test-archive" / "1.0" / "data.zip"
        mock_download_asset.return_value = downloaded_path

        # Get the asset path
        result = await asset_manager.get_asset_path("test-archive")

        # Verify the result - should be the directory, not the file
        expected_path = tmp_path / "dataset" / "test-archive" / "1.0"
        assert result == expected_path

        # Verify the download was called
        mock_download_asset.assert_called_once()

        # Verify the unpack was called
        mock_unpack_asset.assert_called_once()

        # Verify the lock was acquired
        mock_async_asset_lock.assert_called_once()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_creates_metadata(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test that get_asset_path creates metadata after download."""
        # Create a mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add the asset to the manager
        asset_manager.assets = {"test-asset": asset}

        # Set up the cache path
        asset_dir = tmp_path / "model" / "test-asset" / "1.0"
        asset_path = asset_dir / "asset.bin"
        metadata_path = asset_dir / ".asset_info.json"

        # Mock _get_cache_path_for_asset to return our test path
        asset_manager._get_cache_path_for_asset = MagicMock(return_value=asset_dir)

        # Set up the mock download to create a file
        asset_dir.mkdir(parents=True, exist_ok=True)
        mock_download_asset.return_value = asset_path
        with open(asset_path, "w") as f:
            f.write("test data")

        # Mock the async_asset_lock context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None
        mock_async_asset_lock.return_value.__aexit__.return_value = None

        # Call get_asset_path
        result = await asset_manager.get_asset_path("test-asset")

        # Verify the result
        assert result == asset_path
        mock_download_asset.assert_called_once_with(asset)

        # Verify metadata file was created
        assert metadata_path.exists()
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            assert metadata["name"] == "test-asset"
            assert metadata["version"] == "1.0"
            assert metadata["source_type"] == "http"

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_checks_metadata(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test that get_asset_path checks metadata before download."""
        # Create a mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add the asset to the manager
        asset_manager.assets = {"test-asset": asset}

        # Set up the cache path
        asset_dir = tmp_path / "model" / "test-asset" / "1.0"
        asset_path = asset_dir / "asset.bin"
        metadata_path = asset_dir / ".asset_info.json"

        # Mock _get_cache_path_for_asset to return our test path
        asset_manager._get_cache_path_for_asset = MagicMock(return_value=asset_dir)

        # Create the asset directory and file
        asset_dir.mkdir(parents=True, exist_ok=True)
        with open(asset_path, "w") as f:
            f.write("test data")

        # Create metadata file with matching data
        metadata = {
            "name": "test-asset",
            "version": "1.0",
            "asset_type": "model",
            "source_type": "http",
            "checksum": None,
            "unpack": False,
            "unpack_format": None,
            "description": None,
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        # Mock the async_asset_lock context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None
        mock_async_asset_lock.return_value.__aexit__.return_value = None

        # Call get_asset_path
        result = await asset_manager.get_asset_path("test-asset")

        # Verify the result
        assert result == asset_path
        # Download should not be called since metadata matches
        mock_download_asset.assert_not_called()

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_redownloads_on_metadata_mismatch(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test that get_asset_path redownloads if metadata doesn't match."""
        # Create a mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add the asset to the manager
        asset_manager.assets = {"test-asset": asset}

        # Set up the cache path
        asset_dir = tmp_path / "model" / "test-asset" / "1.0"
        asset_path = asset_dir / "asset.bin"
        metadata_path = asset_dir / ".asset_info.json"

        # Mock _get_cache_path_for_asset to return our test path
        asset_manager._get_cache_path_for_asset = MagicMock(return_value=asset_dir)

        # Create the asset directory and file
        asset_dir.mkdir(parents=True, exist_ok=True)
        with open(asset_path, "w") as f:
            f.write("test data")

        # Create metadata file with mismatched data (different version)
        metadata = {
            "name": "test-asset",
            "version": "0.9",  # Different version
            "asset_type": "model",
            "source_type": "http",
            "checksum": None,
            "unpack": False,
            "unpack_format": None,
            "description": None,
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        # Set up the mock download to create a file
        mock_download_asset.return_value = asset_path

        # Mock the async_asset_lock context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None
        mock_async_asset_lock.return_value.__aexit__.return_value = None

        # Call get_asset_path
        result = await asset_manager.get_asset_path("test-asset")

        # Verify the result
        assert result == asset_path
        # Download should be called since metadata doesn't match
        mock_download_asset.assert_called_once_with(asset)

        # Verify metadata file was updated
        with open(metadata_path, "r") as f:
            updated_metadata = json.load(f)
            assert updated_metadata["name"] == "test-asset"
            assert updated_metadata["version"] == "1.0"
            assert updated_metadata["source_type"] == "http"

    @pytest.mark.asyncio
    @patch("openmas.assets.manager.async_asset_lock")
    @patch("openmas.assets.manager.AssetManager.download_asset")
    async def test_get_asset_path_handles_invalid_metadata(
        self, mock_download_asset, mock_async_asset_lock, asset_manager, tmp_path
    ):
        """Test that get_asset_path handles invalid metadata."""
        # Create a mock asset
        asset = AssetConfig(
            name="test-asset",
            version="1.0",
            source=AssetSourceConfig(type="http", url="https://example.com/asset.bin"),
        )

        # Add the asset to the manager
        asset_manager.assets = {"test-asset": asset}

        # Set up the cache path
        asset_dir = tmp_path / "model" / "test-asset" / "1.0"
        asset_path = asset_dir / "asset.bin"
        metadata_path = asset_dir / ".asset_info.json"

        # Mock _get_cache_path_for_asset to return our test path
        asset_manager._get_cache_path_for_asset = MagicMock(return_value=asset_dir)

        # Create the asset directory and file
        asset_dir.mkdir(parents=True, exist_ok=True)
        with open(asset_path, "w") as f:
            f.write("test data")

        # Create invalid metadata file
        with open(metadata_path, "w") as f:
            f.write("not valid json")

        # Set up the mock download to create a file
        mock_download_asset.return_value = asset_path

        # Mock the async_asset_lock context manager
        mock_async_asset_lock.return_value.__aenter__.return_value = None
        mock_async_asset_lock.return_value.__aexit__.return_value = None

        # Call get_asset_path
        result = await asset_manager.get_asset_path("test-asset")

        # Verify the result
        assert result == asset_path
        # Download should be called since metadata is invalid
        mock_download_asset.assert_called_once_with(asset)

        # Verify metadata file was fixed
        assert metadata_path.exists()
        with open(metadata_path, "r") as f:
            metadata = json.load(f)  # Should not raise exception now
            assert metadata["name"] == "test-asset"
            assert metadata["version"] == "1.0"
            assert metadata["source_type"] == "http"
