"""Tests for the OpenMAS asset downloaders."""

import asyncio
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import httpx
import pytest

from openmas.assets.config import AssetSourceConfig
from openmas.assets.downloaders import (
    BaseDownloader,
    HfDownloader,
    HttpDownloader,
    LocalFileHandler,
    get_downloader_for_source,
)
from openmas.assets.exceptions import AssetConfigurationError, AssetDownloadError


# Helper for creating proper async context manager mocks
class AsyncContextManagerMock(AsyncMock):
    """A mock for async context managers."""

    async def __aenter__(self):
        """Implement async enter for context manager protocol."""
        result = await super().__aenter__()
        return result

    async def __aexit__(self, *args):
        """Implement async exit for context manager protocol."""
        await super().__aexit__(*args)


# Improved mock response for HTTP tests
class MockResponse:
    """A mock HTTP response with better async support."""

    def __init__(self, status_code=200, content=b"", headers=None, chunks=None):
        """Initialize the mock response.

        Args:
            status_code: HTTP status code
            content: Response content as bytes
            headers: Response headers
            chunks: Optional list of chunks to return in aiter_bytes
        """
        self.status_code = status_code
        self.reason_phrase = "OK" if status_code < 400 else "Error"
        self.content = content
        self.headers = headers or {}

        if chunks:
            self._chunks = chunks
        else:
            # Split content into 1KB chunks by default
            self._chunks = [content[i : i + 1024] for i in range(0, len(content), 1024)] or [b""]

    async def aiter_bytes(self, chunk_size: int) -> AsyncGenerator[bytes, None]:
        """Async iterator for response chunks."""
        for chunk in self._chunks:
            yield chunk


class TestBaseDownloader:
    """Tests for the BaseDownloader class."""

    def test_download_not_implemented(self) -> None:
        """Test that download() method raises NotImplementedError."""
        downloader = BaseDownloader()
        with pytest.raises(NotImplementedError):
            asyncio.run(downloader.download(MagicMock(spec=AssetSourceConfig), Path()))


class TestHttpDownloader:
    """Tests for the HttpDownloader class."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        downloader = HttpDownloader()
        assert downloader.chunk_size == 8192
        assert downloader.progress_interval_mb == 10
        assert downloader.progress_interval_bytes == 10 * 1024 * 1024

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        downloader = HttpDownloader(chunk_size=4096, progress_interval_mb=5)
        assert downloader.chunk_size == 4096
        assert downloader.progress_interval_mb == 5
        assert downloader.progress_interval_bytes == 5 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_download_invalid_source_type(self) -> None:
        """Test download() with invalid source type."""
        downloader = HttpDownloader()
        # Force disable validation for tests
        with patch("openmas.assets.config.AssetSourceConfig.validate_source_fields"):
            source_config = AssetSourceConfig(type="hf", repo_id="test/model")
            with pytest.raises(AssetConfigurationError) as exc_info:
                await downloader.download(source_config, Path())
            assert "Expected source type 'http'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_missing_url(self) -> None:
        """Test validation and error handling for missing URL in HTTP source."""
        downloader = HttpDownloader()

        # Part 1: Test that Pydantic validation catches the missing URL
        with pytest.raises(ValueError, match="URL is required for HTTP source type"):
            AssetSourceConfig(type="http")

        # Part 2: Test that the downloader itself catches the issue if validation is bypassed
        # This is not a real scenario but ensures the downloader has its own validation
        mock_config = MagicMock(spec=AssetSourceConfig)
        mock_config.type = "http"
        mock_config.url = None

        with pytest.raises(AssetConfigurationError, match="URL is required for HTTP downloads"):
            await downloader.download(mock_config, Path("/tmp/test.txt"))

    @pytest.mark.asyncio
    async def test_download_http_error(self) -> None:
        """Test handling of HTTP error responses."""
        downloader = HttpDownloader()
        source_config = AssetSourceConfig(type="http", url="https://example.com/file.txt")
        target_path = Path("/tmp/test_file.txt")

        # Create a mock response with error status
        mock_response = MockResponse(status_code=404)

        # Create a proper async context manager for the response
        class MockStream:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        # Patch the AsyncClient.stream method directly
        with patch.object(httpx.AsyncClient, "stream", return_value=MockStream()):
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                with pytest.raises(AssetDownloadError) as exc_info:
                    await downloader.download(source_config, target_path)

                assert "HTTP error 404" in str(exc_info.value)
                assert exc_info.value.source_type == "http"
                assert exc_info.value.source_info == "https://example.com/file.txt"
                mock_mkdir.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_request_error(self) -> None:
        """Test handling of request errors from httpx."""
        downloader = HttpDownloader()
        source_config = AssetSourceConfig(type="http", url="https://example.com/file.txt")
        target_path = Path("/tmp/test_file.txt")

        # Mock the httpx client's stream method to raise an error
        with patch.object(httpx.AsyncClient, "stream", side_effect=httpx.RequestError("Connection error")):
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.unlink") as mock_unlink:
                        with pytest.raises(AssetDownloadError) as exc_info:
                            await downloader.download(source_config, target_path)

                        assert "Error downloading asset" in str(exc_info.value)
                        assert "Connection error" in str(exc_info.value)
                        assert exc_info.value.source_type == "http"
                        assert exc_info.value.source_info == "https://example.com/file.txt"
                        mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_success(self) -> None:
        """Test successful download and processing of HTTP response."""
        downloader = HttpDownloader(chunk_size=1024, progress_interval_mb=1)
        source_config = AssetSourceConfig(type="http", url="https://example.com/file.txt")
        target_path = Path("/tmp/test_file.txt")

        # Create mock chunks (3MB of data)
        chunks = [b"x" * 1024 for _ in range(3072)]

        # Create a mock response with the chunks
        mock_response = MockResponse(status_code=200, headers={"content-length": "3145728"}, chunks=chunks)  # 3 MB

        # Create a proper async context manager for the response
        class MockStream:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        # Mock file operations
        mock_file = mock_open()

        with (
            patch.object(httpx.AsyncClient, "stream", return_value=MockStream()),
            patch("pathlib.Path.mkdir"),
            patch("builtins.open", mock_file),
        ):
            await downloader.download(source_config, target_path)

            # Verify that the file was written with the correct data
            write_handle = mock_file()
            assert write_handle.write.call_count == 3072
            for call in write_handle.write.call_args_list:
                assert call[0][0] == b"x" * 1024


class TestHfDownloader:
    """Tests for the HfDownloader class."""

    @pytest.fixture
    def mock_huggingface_available(self) -> MagicMock:
        """Patch the HF_AVAILABLE flag to True and HF_HUB_DOWNLOAD."""
        with patch("openmas.assets.downloaders.HF_AVAILABLE", True):
            mock_hf = MagicMock()
            with patch("openmas.assets.downloaders.HF_HUB_DOWNLOAD", mock_hf):
                yield mock_hf

    @pytest.fixture
    def mock_huggingface_unavailable(self) -> None:
        """Patch the HF_AVAILABLE flag to False."""
        with patch("openmas.assets.downloaders.HF_AVAILABLE", False):
            yield

    def test_init_without_huggingface(self, mock_huggingface_unavailable) -> None:
        """Test initialization when huggingface_hub is not available."""
        with pytest.raises(ImportError) as exc_info:
            HfDownloader()
        assert "Hugging Face Hub is not installed" in str(exc_info.value)

    def test_init_with_default_token(self, mock_huggingface_available) -> None:
        """Test initialization with default token from environment."""
        with patch.dict("os.environ", {"HF_TOKEN": "test_token"}):
            downloader = HfDownloader()
            assert downloader.token == "test_token"

    def test_init_with_custom_token(self, mock_huggingface_available) -> None:
        """Test initialization with custom token."""
        downloader = HfDownloader(token="custom_token")
        assert downloader.token == "custom_token"

    @pytest.mark.asyncio
    async def test_download_invalid_source_type(self, mock_huggingface_available) -> None:
        """Test download() with invalid source type."""
        downloader = HfDownloader()
        # Force disable validation for tests
        with patch("openmas.assets.config.AssetSourceConfig.validate_source_fields"):
            source_config = AssetSourceConfig(type="http", url="https://example.com/file.txt")
            with pytest.raises(AssetConfigurationError) as exc_info:
                await downloader.download(source_config, Path())
            assert "Expected source type 'hf'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_missing_repo_id(self, mock_huggingface_available) -> None:
        """Test validation and error handling for missing repo_id in HF source."""
        downloader = HfDownloader()

        # Part 1: Test that Pydantic validation catches the missing repo_id
        with pytest.raises(ValueError, match="repo_id is required for Hugging Face source type"):
            AssetSourceConfig(type="hf")

        # Part 2: Test that the downloader itself catches the issue if validation is bypassed
        # This is not a real scenario but ensures the downloader has its own validation
        mock_config = MagicMock(spec=AssetSourceConfig)
        mock_config.type = "hf"
        mock_config.repo_id = None

        with pytest.raises(AssetConfigurationError, match="repo_id is required for Hugging Face Hub downloads"):
            await downloader.download(mock_config, Path("/tmp/model.bin"))

    @pytest.mark.asyncio
    async def test_download_success(self, mock_huggingface_available) -> None:
        """Test successful download."""
        downloader = HfDownloader(token="test_token")
        source_config = AssetSourceConfig(type="hf", repo_id="test/model", filename="model.bin", revision="main")
        target_path = Path("/tmp/model.bin")
        cache_dir = target_path.parent / ".hf-cache"

        # Mock the hf_hub_download function
        mock_download_path = Path("/tmp/.hf-cache/downloaded_file.bin")
        mock_huggingface_available.return_value = mock_download_path

        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),  # All paths exist
            patch("pathlib.Path.unlink"),
            patch("shutil.move") as mock_move,
            patch("shutil.rmtree") as mock_rmtree,
            patch("asyncio.to_thread", AsyncMock(side_effect=lambda f: f())),
        ):
            await downloader.download(source_config, target_path)

            # Verify that hf_hub_download was called with the correct arguments
            mock_huggingface_available.assert_called_once_with(
                repo_id="test/model",
                filename="model.bin",
                revision="main",
                token="test_token",
                cache_dir=cache_dir,
            )

            # Verify that shutil.move was called to move the downloaded file
            mock_move.assert_called_once_with(mock_download_path, target_path)
            # Verify cache directory cleanup
            mock_rmtree.assert_called_once_with(cache_dir)

    @pytest.mark.asyncio
    async def test_download_error(self, mock_huggingface_available) -> None:
        """Test download() with an error from huggingface_hub."""
        downloader = HfDownloader()
        # Force disable validation for tests
        with patch("openmas.assets.config.AssetSourceConfig.validate_source_fields", return_value=None):
            source_config = AssetSourceConfig(type="hf", repo_id="test/model", filename="model.bin")
            target_path = Path("/tmp/model.bin")

            # Mock the hf_hub_download function to raise an exception
            mock_huggingface_available.side_effect = Exception("HF download error")

            with (
                patch("pathlib.Path.mkdir"),
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.unlink") as mock_unlink,
                patch("asyncio.to_thread", AsyncMock(side_effect=lambda f: f())),
            ):
                with pytest.raises(AssetDownloadError) as exc_info:
                    await downloader.download(source_config, target_path)

                assert "Error downloading asset from Hugging Face Hub" in str(exc_info.value)
                assert "HF download error" in str(exc_info.value)
                assert exc_info.value.source_type == "hf"
                assert exc_info.value.source_info == "test/model/model.bin"
                # Verify that the target file was cleaned up
                mock_unlink.assert_called_once()


class TestLocalFileHandler:
    """Tests for the LocalFileHandler class."""

    @pytest.mark.asyncio
    async def test_download_invalid_source_type(self) -> None:
        """Test download() with invalid source type."""
        handler = LocalFileHandler()
        # Force disable validation for tests
        with patch("openmas.assets.config.AssetSourceConfig.validate_source_fields"):
            source_config = AssetSourceConfig(type="http", url="https://example.com/file.txt")
            with pytest.raises(AssetConfigurationError) as exc_info:
                await handler.download(source_config, Path())
            assert "Expected source type 'local'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_missing_path(self) -> None:
        """Test validation and error handling for missing path in local source."""
        handler = LocalFileHandler()

        # Part 1: Test that Pydantic validation catches the missing path
        with pytest.raises(ValueError, match="path is required for local source type"):
            AssetSourceConfig(type="local")

        # Part 2: Test that the handler itself catches the issue if validation is bypassed
        # This is not a real scenario but ensures the handler has its own validation
        mock_config = MagicMock(spec=AssetSourceConfig)
        mock_config.type = "local"
        mock_config.path = None

        with pytest.raises(AssetConfigurationError, match="path is required for local file sources"):
            await handler.download(mock_config, Path("/tmp/test.txt"))

    @pytest.mark.asyncio
    async def test_download_nonexistent_source(self) -> None:
        """Test download() with nonexistent source path."""
        handler = LocalFileHandler()
        # Force disable validation for tests
        with patch("openmas.assets.config.AssetSourceConfig.validate_source_fields"):
            source_config = AssetSourceConfig(type="local", path=Path("/nonexistent/path"))
            target_path = Path("/tmp/target.txt")

            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(AssetDownloadError) as exc_info:
                    await handler.download(source_config, target_path)
                assert "Local source path does not exist" in str(exc_info.value)
                assert exc_info.value.source_type == "local"
                source_info = exc_info.value.source_info
                assert source_info is not None and "/nonexistent/path" in source_info

    @pytest.mark.asyncio
    async def test_download_file_success(self) -> None:
        """Test successful file copy."""
        handler = LocalFileHandler()
        source_path = Path("/source/file.txt")
        target_path = Path("/tmp/target.txt")
        source_config = AssetSourceConfig(type="local", path=source_path)

        with (
            patch("pathlib.Path.exists", return_value=True),  # All paths exist
            patch("pathlib.Path.is_dir", return_value=False),  # Not a directory
            patch("pathlib.Path.mkdir"),  # Allow mkdir
            patch("pathlib.Path.unlink"),  # Allow unlink without error
            patch("shutil.copy2") as mock_copy,  # Capture copy2 calls
        ):
            await handler.download(source_config, target_path)

            # Verify copy2 was called with the correct paths
            mock_copy.assert_called_once_with(source_path, target_path)

    @pytest.mark.asyncio
    async def test_download_directory_success(self) -> None:
        """Test successful directory copy."""
        handler = LocalFileHandler()
        source_path = Path("/source/directory")
        target_path = Path("/tmp/target_directory")
        source_config = AssetSourceConfig(type="local", path=source_path)

        # We'll create a sequence of responses - source_path exists but target_path doesn't
        exist_values = [True, False]
        exist_mock = MagicMock(side_effect=exist_values)

        with (
            patch("pathlib.Path.exists", new=exist_mock),
            patch("pathlib.Path.is_dir", return_value=True),  # It's a directory
            patch("pathlib.Path.mkdir"),  # Allow mkdir
            patch("shutil.rmtree") as mock_rmtree,  # Capture rmtree calls
            patch("shutil.copytree") as mock_copytree,  # Capture copytree calls
        ):
            await handler.download(source_config, target_path)

            # Verify copytree was called with the correct paths, without symlinks
            mock_copytree.assert_called_once_with(source_path, target_path)
            # Verify rmtree was not called (target directory shouldn't exist yet)
            mock_rmtree.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_directory_with_existing_target(self) -> None:
        """Test directory copy with existing target directory."""
        handler = LocalFileHandler()
        source_path = Path("/source/directory")
        target_path = Path("/tmp/target_directory")
        source_config = AssetSourceConfig(type="local", path=source_path)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("shutil.rmtree") as mock_rmtree,
            patch("shutil.copytree") as mock_copytree,
        ):
            await handler.download(source_config, target_path)

            # Verify rmtree was called to remove the existing directory
            mock_rmtree.assert_called_once_with(target_path)
            # Verify copytree was called with the correct paths, without symlinks
            mock_copytree.assert_called_once_with(source_path, target_path)

    @pytest.mark.asyncio
    async def test_download_error(self) -> None:
        """Test handling of a copy error for local files."""
        handler = LocalFileHandler()
        source_path = Path("/source/file.txt")
        target_path = Path("/tmp/target.txt")
        source_config = AssetSourceConfig(type="local", path=source_path)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=False),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.unlink"),  # Mock unlink to avoid the FileNotFoundError
            patch("shutil.copy2", side_effect=PermissionError("Permission denied")),
        ):
            with pytest.raises(AssetDownloadError) as exc_info:
                await handler.download(source_config, target_path)
            assert "Error copying local asset" in str(exc_info.value)
            assert "Permission denied" in str(exc_info.value)
            assert exc_info.value.source_type == "local"
            source_info = exc_info.value.source_info
            assert source_info is not None and str(source_path) in source_info


class TestGetDownloaderForSource:
    """Tests for the get_downloader_for_source function."""

    def test_get_http_downloader(self) -> None:
        """Test getting a downloader for HTTP source."""
        source_config = AssetSourceConfig(type="http", url="https://example.com/file.txt")
        downloader = get_downloader_for_source(source_config)
        assert isinstance(downloader, HttpDownloader)

    def test_get_local_file_handler(self) -> None:
        """Test getting a downloader for local source."""
        source_config = AssetSourceConfig(type="local", path=Path("/some/path"))
        downloader = get_downloader_for_source(source_config)
        assert isinstance(downloader, LocalFileHandler)

    def test_get_hf_downloader(self) -> None:
        """Test getting a downloader for Hugging Face source."""
        source_config = AssetSourceConfig(type="hf", repo_id="test/model")
        # Patch HF_AVAILABLE to True
        with patch("openmas.assets.downloaders.HF_AVAILABLE", True):
            # Patch hf_hub_download to prevent ImportError
            with patch("openmas.assets.downloaders.HF_HUB_DOWNLOAD", MagicMock()):
                downloader = get_downloader_for_source(source_config)
                assert isinstance(downloader, HfDownloader)

    def test_get_hf_downloader_not_available(self) -> None:
        """Test getting a downloader for Hugging Face source when not available."""
        source_config = AssetSourceConfig(type="hf", repo_id="test/model")
        # Patch HF_AVAILABLE to False
        with patch("openmas.assets.downloaders.HF_AVAILABLE", False):
            with pytest.raises(AssetConfigurationError, match="Hugging Face Hub is not installed"):
                get_downloader_for_source(source_config)

    def test_get_unknown_downloader(self) -> None:
        """Test getting a downloader for unknown source type."""
        # Use patch to bypass validation
        with patch("openmas.assets.config.AssetSourceConfig.validate_source_fields"):
            source_config = MagicMock(spec=AssetSourceConfig)
            source_config.type = "unknown"
            with pytest.raises(AssetConfigurationError) as exc_info:
                get_downloader_for_source(source_config)
            assert "Unknown source type: unknown" in str(exc_info.value)
