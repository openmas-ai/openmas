"""Tests for the OpenMAS asset downloaders."""

import logging
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock, call, mock_open, patch

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
        return self

    async def __aexit__(self, *args):
        """Implement async exit for context manager protocol."""
        pass


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
        if self._chunks:
            for chunk in self._chunks:
                yield chunk
        elif self.content:
            for i in range(0, len(self.content), chunk_size):
                yield self.content[i : i + chunk_size]


class TestBaseDownloader:
    """Tests for the BaseDownloader class."""

    @pytest.mark.asyncio
    async def test_download_not_implemented(self) -> None:
        """Test that download() method raises NotImplementedError."""
        downloader = BaseDownloader()
        with pytest.raises(NotImplementedError):
            await downloader.download(MagicMock(spec=AssetSourceConfig), Path())


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

        # Create a mock config that mimics AssetSourceConfig but has an invalid type for HttpDownloader
        mock_source_config = MagicMock(spec=AssetSourceConfig)
        mock_source_config.type = "hf"  # Invalid type for HttpDownloader
        mock_source_config.url = "http://example.com/fake"  # HttpDownloader checks for url, so provide one
        # Ensure other attributes accessed by getattr in the downloader have defaults if not explicitly set by test
        # For progress_report, getattr in downloader will default to True if not present.
        # mock_source_config.progress_report = True # Or let getattr handle it
        # mock_source_config.authentication = None # Default for this test

        with pytest.raises(AssetConfigurationError) as exc_info:
            await downloader.download(mock_source_config, Path("/tmp/test.txt"))
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
            for call_instance in write_handle.write.call_args_list:
                assert call_instance[0][0] == b"x" * 1024

    @pytest.mark.asyncio
    async def test_download_with_progress_disabled(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no progress-specific logs are emitted when progress_report is False."""
        caplog.set_level(logging.INFO)

        source_config = AssetSourceConfig(
            type="http",
            url="http://example.com/file.dat",
            progress_report=False,  # Explicitly disable
            # progress_report_interval_mb=1 # Interval doesn't matter if disabled, but HttpDownloader will use its default if not set
        )
        target_path = tmp_path / "file.dat"

        downloader = HttpDownloader()  # Uses default chunk_size and progress_interval_mb

        # Mock response data
        mock_file_content = b"chunk1data" + b"chunk2data"
        mock_response = MockResponse(
            status_code=200,
            headers={"content-length": str(len(mock_file_content))},
            chunks=[b"chunk1data", b"chunk2data"],
        )

        # Create a proper async context manager for the mock response for client.stream
        class MockStreamContextManager:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        mock_file_open = mock_open()

        with patch("openmas.assets.downloaders.httpx.AsyncClient") as mock_async_client_constructor:
            # Configure the mock client instance that AsyncClient() will return
            mock_client_instance = MagicMock()
            mock_client_instance.stream.return_value = MockStreamContextManager()
            mock_async_client_constructor.return_value.__aenter__.return_value = (
                mock_client_instance  # for 'async with httpx.AsyncClient(...) as client:'
            )

            with patch("pathlib.Path.mkdir") as mock_mkdir, patch("builtins.open", mock_file_open):
                await downloader.download(source_config, target_path)

        # Check that target directory was created
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify file content was written
        mock_file_open().write.assert_has_calls(
            [
                call(b"chunk1data"),
                call(b"chunk2data"),
            ]
        )

        # Assert that NO progress-specific log messages are present
        # This includes both interval logs and the final "Download complete: X.XX MB" log,
        # as they are conditional on 'use_progress_reporting' which should be False.
        progress_log_found = False
        for record in caplog.records:
            if "Download progress:" in record.message or "Download complete:" in record.message:
                progress_log_found = True
                print(f"Unexpected progress log found: {record.message}")  # For debugging if test fails

        assert (
            not progress_log_found
        ), "No progress-specific (interval or final) log messages should be present when progress_report is False."

        # Check that the initial informational log is still there
        assert any(
            f"Downloading asset from http://example.com/file.dat to {target_path}" in rec.message
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    @patch("openmas.assets.downloaders.httpx.AsyncClient")
    @patch("openmas.assets.downloaders.TQDM_AVAILABLE", True)
    @patch("openmas.assets.downloaders.tqdm", create=True)
    @patch("sys.stdout.isatty", return_value=True)  # Simulate a TTY environment
    async def test_download_with_tqdm_progress_enabled_tty(
        self,
        mock_isatty: MagicMock,
        mock_tqdm_constructor: MagicMock,
        mock_async_client_constructor: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Tests that tqdm is used when progress_report is True and stdout is a TTY."""
        caplog.set_level(logging.INFO)
        source_config = AssetSourceConfig(
            type="http",
            url="http://example.com/largefile.dat",
            progress_report=True,  # Enabled
            progress_report_interval_mb=1,
        )
        target_path = tmp_path / "largefile.dat"
        downloader = HttpDownloader()  # Uses default chunk_size from its init

        # Simulate multiple chunks for tqdm updates
        # Total size: 1MB, chunk_size in HttpDownloader is 8192 by default
        total_size_bytes = 1 * 1024 * 1024
        downloader_chunk_size = downloader.chunk_size  # Typically 8192
        num_chunks = (total_size_bytes + downloader_chunk_size - 1) // downloader_chunk_size  # Ceiling division

        chunks_data = [os.urandom(downloader_chunk_size) for _ in range(num_chunks - 1)]
        # Last chunk might be smaller
        last_chunk_size = total_size_bytes - (num_chunks - 1) * downloader_chunk_size
        if last_chunk_size > 0:
            chunks_data.append(os.urandom(last_chunk_size))
        else:  # if total_size_bytes is a multiple of chunk_size, num_chunks was exact
            # and last_chunk_size calculation would be 0 or negative if not handled.
            # If it was perfectly divisible, the loop for num_chunks-1 handles all but one full last chunk
            if total_size_bytes % downloader_chunk_size == 0 and num_chunks > 0:
                chunks_data.append(os.urandom(downloader_chunk_size))
            elif num_chunks == 0 and total_size_bytes > 0:  # very small file, less than one chunk
                chunks_data = [os.urandom(total_size_bytes)]
            elif total_size_bytes == 0:
                chunks_data = [b""]

        mock_response = MockResponse(
            status_code=200, headers={"content-length": str(total_size_bytes)}, chunks=chunks_data
        )

        class MockStreamContextManager:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        mock_client_instance = MagicMock()
        mock_client_instance.stream.return_value = MockStreamContextManager()
        mock_async_client_constructor.return_value.__aenter__.return_value = mock_client_instance

        # Mock the tqdm instance that the constructor will return
        mock_tqdm_instance = MagicMock()
        mock_tqdm_constructor.return_value.__enter__.return_value = mock_tqdm_instance  # For 'with tqdm(...) as pbar:'
        mock_file_open = mock_open()

        with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_file_open):
            await downloader.download(source_config, target_path)

        mock_isatty.assert_called()  # Ensure tty check happened
        # Check TQDM_AVAILABLE, if it was False, tqdm wouldn't be called.
        # Assuming TQDM_AVAILABLE is True for this test path, or mock it too.
        mock_tqdm_constructor.assert_called_once()  # tqdm should have been initialized
        assert mock_tqdm_instance.update.call_count == len(
            chunks_data
        ), f"Expected {len(chunks_data)} tqdm updates, got {mock_tqdm_instance.update.call_count}"

        # Ensure no fallback interval-based log messages for progress appear when tqdm is active
        progress_log_found = False
        for record in caplog.records:
            if "Download progress:" in record.message and "%" in record.message:
                progress_log_found = True
        assert not progress_log_found, "Fallback progress logs should not appear when tqdm is active."

        # Final "Download complete" log is still expected if progress_report is True
        assert any(
            f"Download complete: {total_size_bytes / (1024 * 1024):.2f} MB" in rec.message for rec in caplog.records
        )

    @pytest.mark.asyncio
    @patch("openmas.assets.downloaders.httpx.AsyncClient")
    @patch("openmas.assets.downloaders.TQDM_AVAILABLE", True)
    @patch("openmas.assets.downloaders.tqdm", create=True)
    @patch("sys.stdout.isatty", return_value=False)  # Simulate a NON-TTY environment
    async def test_download_with_progress_enabled_non_tty(
        self,
        mock_isatty: MagicMock,
        mock_tqdm_constructor: MagicMock,
        mock_async_client_constructor: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Tests that fallback interval logging is used when progress_report is True but stdout is NOT a TTY."""
        caplog.set_level(logging.INFO)

        # Small interval to ensure logs trigger with small data
        # Content size should be more than 1 interval to see interval log
        progress_mb_interval = 0.01  # 10KB interval
        content_size_bytes = int(progress_mb_interval * 1024 * 1024 * 2.5)  # 25KB of data

        source_config = AssetSourceConfig(
            type="http",
            url="http://example.com/anotherfile.dat",
            progress_report=True,  # Enabled
            progress_report_interval_mb=progress_mb_interval,
        )
        target_path = tmp_path / "anotherfile.dat"
        # Downloader uses its own chunk_size (8192), and progress_interval_mb from source_config if provided
        downloader = HttpDownloader()

        downloader_chunk_size = downloader.chunk_size
        num_chunks = (content_size_bytes + downloader_chunk_size - 1) // downloader_chunk_size
        chunks_data = []
        remaining_bytes = content_size_bytes
        for _ in range(num_chunks):
            current_chunk_size = min(remaining_bytes, downloader_chunk_size)
            chunks_data.append(os.urandom(current_chunk_size))
            remaining_bytes -= current_chunk_size
            if remaining_bytes <= 0:
                break
        if not chunks_data and content_size_bytes > 0:
            chunks_data = [os.urandom(content_size_bytes)]
        elif content_size_bytes == 0:
            chunks_data = [b""]

        mock_response = MockResponse(
            status_code=200, headers={"content-length": str(content_size_bytes)}, chunks=chunks_data
        )

        class MockStreamContextManager:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        mock_client_instance = MagicMock()
        mock_client_instance.stream.return_value = MockStreamContextManager()
        mock_async_client_constructor.return_value.__aenter__.return_value = mock_client_instance
        mock_file_open = mock_open()

        with patch("pathlib.Path.mkdir"), patch("builtins.open", mock_file_open):
            await downloader.download(source_config, target_path)

        mock_isatty.assert_called()
        mock_tqdm_constructor.assert_not_called()  # tqdm should NOT have been initialized

        # Check for fallback progress logs
        # Example: "Download progress: 0.01 MB / 0.02 MB (XX.X%)"
        found_progress_log = any(
            "Download progress:" in rec.message and "%" in rec.message and "MB /" in rec.message
            for rec in caplog.records
        )
        # We expect at least one interval log if content_size > progress_interval_bytes
        expected_progress_interval_bytes = int(progress_mb_interval * 1024 * 1024)
        if content_size_bytes > expected_progress_interval_bytes:
            assert (
                found_progress_log
            ), f"Fallback interval-based progress logs should appear in non-TTY. Interval bytes: {expected_progress_interval_bytes}, Content bytes: {content_size_bytes}"
        else:
            assert (
                not found_progress_log
            ), "Fallback interval-based progress logs should NOT appear if content is smaller than one interval."

        # Final "Download complete" log is still expected
        assert any(
            f"Download complete: {content_size_bytes / (1024 * 1024):.2f} MB" in rec.message for rec in caplog.records
        )


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
            # The token is now retrieved during download, not initialization
            assert downloader.token is None

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
        """Test successful download with mocked huggingface_hub."""
        source_config = AssetSourceConfig(type="hf", repo_id="user/model", filename="model.bin")
        target_path = Path("/tmp/test_file.txt")

        # Mock the _download method to avoid actual file operations
        mock_download_result = target_path

        with patch.object(HfDownloader, "_download", return_value=mock_download_result) as mock_download:
            downloader = HfDownloader()
            await downloader.download(source_config, target_path)

            # Check that _download was called with the right arguments
            mock_download.assert_called_once()
            call_args = mock_download.call_args[0]
            assert call_args[0] == "user/model"  # repo_id
            assert call_args[1] == "model.bin"  # filename
            assert call_args[2] == "main"  # revision
            assert call_args[3] is None  # token
            assert call_args[4] == target_path  # target_path

    @pytest.mark.asyncio
    async def test_download_error(self, mock_huggingface_available) -> None:
        """Test download() with an error from huggingface_hub."""
        downloader = HfDownloader()
        # Force disable validation for tests
        with patch("openmas.assets.config.AssetSourceConfig.validate_source_fields", return_value=None):
            source_config = AssetSourceConfig(type="hf", repo_id="test/model", filename="model.bin")
            target_path = Path("/tmp/model.bin")

            # Create a mock for _download that raises an exception
            error_msg = "HF download error"
            mock_download = MagicMock(side_effect=Exception(error_msg))

            with patch.object(downloader, "_download", mock_download):
                with pytest.raises(AssetDownloadError) as exc_info:
                    await downloader.download(source_config, target_path)

                assert "Error downloading from Hugging Face Hub" in str(exc_info.value)
                assert error_msg in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_with_progress_enabled(
        self, mock_huggingface_available: MagicMock, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that progress reporting is enabled and env var is managed for HF downloads."""
        source_config = AssetSourceConfig(
            type="hf",
            repo_id="user/model_prog_enabled",
            filename="model.bin",
            progress_report=True,  # Progress reporting enabled
        )
        target_path = tmp_path / "model_prog_enabled.bin"
        downloader = HfDownloader()

        # This will be the state of HF_HUB_DISABLE_PROGRESS_BARS when _download (and thus hf_hub_download) is called
        env_var_at_internal_download_call_time = "initial_unset_value"  # A sentinel

        def mock_internal_download_side_effect(repo_id_arg, filename_arg, revision_arg, token_arg, target_path_arg):
            nonlocal env_var_at_internal_download_call_time
            env_var_at_internal_download_call_time = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
            target_path_arg.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path_arg, "w") as f:
                f.write("mock content for progress_enabled test")
            return target_path_arg

        # Patch downloader._download method directly
        mock_internal_dl_method = MagicMock(side_effect=mock_internal_download_side_effect)

        # Initial state of env var for the test
        initial_env_for_test = {"HF_HUB_DISABLE_PROGRESS_BARS": "1"}

        with (
            patch.object(downloader, "_download", mock_internal_dl_method),
            patch.dict(os.environ, initial_env_for_test, clear=True),
            patch("openmas.assets.downloaders.logger") as mock_logger,
        ):  # Ensure logger is the one from downloaders
            await downloader.download(source_config, target_path)

            mock_internal_dl_method.assert_called_once_with(
                source_config.repo_id,
                source_config.filename,
                source_config.revision or "main",
                None,  # Expect None for token as downloader.token is None and no auth in source_config
                target_path,
            )

            # Assert that when _download (and thus hf_hub_download) was called,
            # HF_HUB_DISABLE_PROGRESS_BARS was NOT "1" (should have been deleted by the try block)
            assert (
                env_var_at_internal_download_call_time is None
            ), f"Expected HF_HUB_DISABLE_PROGRESS_BARS to be None during internal download, got '{env_var_at_internal_download_call_time}'"

            # Assert that the correct INFO log for enabled progress was made
            mock_logger.info.assert_any_call(
                f"Downloading asset '{source_config.repo_id}/{source_config.filename}' (progress display managed by Hugging Face Hub)"
            )
            # Assert that the DEBUG log for disabling progress was NOT made
            disabled_log_found = any(
                "Disabled Hugging Face Hub progress bars" in call_args[0][0]
                for call_args in mock_logger.debug.call_args_list
            )
            assert (
                not disabled_log_found
            ), "Debug log for disabling progress should not be present when progress is enabled"

            # After the downloader.download call, the finally block should have restored the original env var value ("1")
            assert (
                os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS") == "1"
            ), "Expected HF_HUB_DISABLE_PROGRESS_BARS to be restored to its original value ('1') after download call."

    @pytest.mark.asyncio
    async def test_download_with_progress_disabled(
        self, mock_huggingface_available: MagicMock, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that HF_HUB_DISABLE_PROGRESS_BARS is set when progress_report is False and then restored."""
        # mock_huggingface_available fixture ensures HF_AVAILABLE is True and HF_HUB_DOWNLOAD is a mock

        caplog.set_level(logging.DEBUG)  # To see "Disabled Hugging Face Hub progress bars..." log

        source_config = AssetSourceConfig(
            type="hf",
            repo_id="user/model_no_progress",
            filename="model.bin",
            progress_report=False,  # Explicitly disable progress
        )
        target_path = tmp_path / "model.bin"
        downloader = HfDownloader()

        # Ensure the mock for HF_HUB_DOWNLOAD (from mock_huggingface_available) is correctly configured
        # The fixture patches 'openmas.assets.downloaders.HF_HUB_DOWNLOAD'
        # We need to control its side_effect here to check env var
        env_var_at_call_time = None
        original_hf_hub_download_mock = mock_huggingface_available  # This is the mock from the fixture

        def check_env_var_side_effect(*args: Any, **kwargs: Any) -> str:
            nonlocal env_var_at_call_time
            env_var_at_call_time = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
            # Simulate hf_hub_download by creating the file it's supposed to download
            # The _download method expects this file to exist to then move it.
            actual_download_target_dir = Path(kwargs.get("local_dir"))
            actual_download_filename = (
                Path(kwargs.get("filename")) if kwargs.get("filename") else Path(args[1] or "default_filename")
            )
            final_simulated_path = actual_download_target_dir / actual_download_filename

            final_simulated_path.parent.mkdir(parents=True, exist_ok=True)
            with open(final_simulated_path, "w") as f:
                f.write("mock content")
            return str(final_simulated_path)

        original_hf_hub_download_mock.side_effect = check_env_var_side_effect

        # Test with os.environ initially clean for this key
        with patch.dict(os.environ, {}, clear=True):
            assert "HF_HUB_DISABLE_PROGRESS_BARS" not in os.environ

            await downloader.download(source_config, target_path)

            original_hf_hub_download_mock.assert_called_once()
            # Verify call arguments if necessary, e.g., repo_id, filename, token etc.
            call_kwargs = original_hf_hub_download_mock.call_args.kwargs
            assert call_kwargs.get("repo_id") == source_config.repo_id
            assert call_kwargs.get("filename") == source_config.filename
            assert (
                call_kwargs.get("local_dir") == target_path.parent
            )  # _download passes target_path.parent as local_dir

            assert (
                env_var_at_call_time == "1"
            ), "HF_HUB_DISABLE_PROGRESS_BARS should be '1' during hf_hub_download call when progress_report is False."

            # Assert that it's restored to its original state (None in this case)
            assert (
                "HF_HUB_DISABLE_PROGRESS_BARS" not in os.environ
            ), "HF_HUB_DISABLE_PROGRESS_BARS should be restored to its original state (None) after the call."

            # Assert logger message for disabling progress
            assert any(
                "Disabled Hugging Face Hub progress bars as per configuration" in rec.message for rec in caplog.records
            ), "Log message for disabling HF progress not found."

            # Assert successful download log
            assert any(
                f"Successfully downloaded asset from Hugging Face Hub to {target_path}" in rec.message
                for rec in caplog.records
            )
            assert target_path.exists()
            assert target_path.read_text() == "mock content"

    # Parameterize to cover different initial states and progress_report settings
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "initial_env_value, progress_report_config, expected_final_env_value",
        [
            (None, False, None),  # Progress disabled, env var initially None -> restored to None
            ("original_0", False, "original_0"),  # Progress disabled, env var initially "0" -> restored to "0"
            ("1", True, "1"),  # Progress enabled, env var initially "1" (we delete, then restore) -> restored to "1"
            (None, True, None),  # Progress enabled, env var initially None (we do nothing, stays None) -> remains None
            ("0", True, "0"),  # Progress enabled, env var initially "0" (we delete, then restore) -> restored to "0"
        ],
    )
    async def test_progress_setting_is_restored_on_error(
        self,
        mock_huggingface_available: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        initial_env_value: Optional[str],
        progress_report_config: bool,
        expected_final_env_value: Optional[str],
    ) -> None:
        """Test that original HF_HUB_DISABLE_PROGRESS_BARS is restored even after exceptions from HF_HUB_DOWNLOAD."""
        caplog.set_level(logging.DEBUG)
        downloader = HfDownloader()
        target_path = tmp_path / "test_hf_error_file.txt"
        error_to_raise = AssetDownloadError("Simulated download failure from hf_hub_download")

        source_config = AssetSourceConfig(
            type="hf",
            repo_id="user/model_error_restore",
            filename="model_error.bin",
            progress_report=progress_report_config,
        )

        # Setup initial environment state for HF_HUB_DISABLE_PROGRESS_BARS
        current_os_environ_setup = {}
        if initial_env_value is not None:
            current_os_environ_setup["HF_HUB_DISABLE_PROGRESS_BARS"] = initial_env_value

        # Ensure the mock for HF_HUB_DOWNLOAD (from mock_huggingface_available fixture) raises an error
        hf_mock = mock_huggingface_available
        hf_mock.side_effect = error_to_raise
        hf_mock.reset_mock()  # Reset from previous test if any

        with patch.dict(os.environ, current_os_environ_setup, clear=True):
            # Verify initial state inside the patched environment
            assert os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS") == initial_env_value

            with pytest.raises(AssetDownloadError, match="Simulated download failure"):
                await downloader.download(source_config, target_path)

            hf_mock.assert_called_once()

            # Check that os.environ is restored correctly after the exception
            final_value_in_os_environ = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
            assert (
                final_value_in_os_environ == expected_final_env_value
            ), f"Test Case: initial='{initial_env_value}', progress_report={progress_report_config}. Expected final='{expected_final_env_value}', got='{final_value_in_os_environ}'"

            # Specific logging checks based on progress_report_config
            if progress_report_config:  # Progress enabled
                assert any(
                    f"Downloading asset '{source_config.repo_id}/{source_config.filename}' (progress display managed by Hugging Face Hub)"
                    in rec.message
                    for rec in caplog.records
                ), "Expected 'Downloading asset (progress managed by Hugging Face Hub)' log when progress_report=True"
                # When progress_report is True, we don't log about *disabling* bars.
                assert not any("Disabled Hugging Face Hub progress bars" in rec.message for rec in caplog.records)
            else:  # Progress disabled
                assert any(
                    "Disabled Hugging Face Hub progress bars as per configuration" in rec.message
                    for rec in caplog.records
                ), "Expected 'Disabled Hugging Face Hub progress bars' log when progress_report=False"
                assert not any(
                    "Downloading asset '(progress display managed by Hugging Face Hub)" in rec.message
                    for rec in caplog.records
                )


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
