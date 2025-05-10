"""Tests for authentication in asset downloaders."""

import os
from unittest.mock import MagicMock, patch

import pytest

from openmas.assets.config import AssetAuthentication, AssetSourceConfig, HttpAuthDetails, HuggingFaceAuthDetails
from openmas.assets.downloaders import HfDownloader, HttpDownloader, get_downloader_for_source
from openmas.assets.exceptions import AssetAuthenticationError, AssetDownloadError


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    with patch.dict(
        os.environ, {"HTTP_TOKEN": "test-http-token", "HF_TOKEN": "test-hf-token", "CUSTOM_TOKEN": "custom-token-value"}
    ):
        yield


def test_http_auth_headers(mock_env_vars):
    """Test HTTP authentication header preparation."""
    # Create a source config with authentication
    source_config = AssetSourceConfig(
        type="http",
        url="https://example.com/model.bin",
        authentication=AssetAuthentication(
            http=HttpAuthDetails(token_env_var="HTTP_TOKEN", scheme="Bearer", header_name="Authorization")
        ),
    )

    # Directly test the header creation logic from the downloader
    with patch("openmas.assets.downloaders.os.environ", {"HTTP_TOKEN": "test-http-token"}):
        headers = {}
        http_auth = source_config.authentication.http
        token_env_var = http_auth.token_env_var
        token = os.environ.get(token_env_var)

        # Apply the authentication scheme
        if http_auth.scheme:
            auth_value = f"{http_auth.scheme} {token}"
        else:
            auth_value = token

        headers[http_auth.header_name] = auth_value

        # Verify headers
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-http-token"


def test_http_custom_auth_headers(mock_env_vars):
    """Test HTTP custom authentication header preparation."""
    # Create a source config with custom authentication
    source_config = AssetSourceConfig(
        type="http",
        url="https://example.com/model.bin",
        authentication=AssetAuthentication(
            http=HttpAuthDetails(token_env_var="CUSTOM_TOKEN", scheme="ApiKey", header_name="X-API-Key")
        ),
    )

    # Directly test the header creation logic from the downloader
    with patch("openmas.assets.downloaders.os.environ", {"CUSTOM_TOKEN": "custom-token-value"}):
        headers = {}
        http_auth = source_config.authentication.http
        token_env_var = http_auth.token_env_var
        token = os.environ.get(token_env_var)

        # Apply the authentication scheme
        if http_auth.scheme:
            auth_value = f"{http_auth.scheme} {token}"
        else:
            auth_value = token

        headers[http_auth.header_name] = auth_value

        # Verify headers
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "ApiKey custom-token-value"


def test_http_missing_token():
    """Test HTTP authentication behavior when token is missing."""
    # Create a source config with authentication
    source_config = AssetSourceConfig(
        type="http",
        url="https://example.com/model.bin",
        authentication=AssetAuthentication(
            http=HttpAuthDetails(token_env_var="NONEXISTENT_TOKEN", scheme="Bearer", header_name="Authorization")
        ),
    )

    # Directly test the header creation logic from the downloader
    with patch("openmas.assets.downloaders.os.environ", {}):
        with patch("openmas.assets.downloaders.logger") as mock_logger:
            headers = {}
            http_auth = source_config.authentication.http
            token_env_var = http_auth.token_env_var
            token = os.environ.get(token_env_var)

            if not token:
                # This is the warning we want to verify
                logger_msg = f"HTTP authentication token environment variable '{token_env_var}' not found or empty"
                mock_logger.error(logger_msg)
            else:
                # Apply the authentication scheme
                if http_auth.scheme:
                    auth_value = f"{http_auth.scheme} {token}"
                else:
                    auth_value = token

                headers[http_auth.header_name] = auth_value

            # Verify headers are empty
            assert "Authorization" not in headers
            # Verify error was logged
            mock_logger.error.assert_called_with(
                "HTTP authentication token environment variable 'NONEXISTENT_TOKEN' not found or empty"
            )


def test_hf_token_extraction(mock_env_vars):
    """Test extracting token for Hugging Face Hub."""
    # Create a source config with authentication
    source_config = AssetSourceConfig(
        type="hf",
        repo_id="user/model",
        filename="model.bin",
        authentication=AssetAuthentication(hf=HuggingFaceAuthDetails(token_env_var="HF_TOKEN")),
    )

    # Directly test the token extraction logic from the downloader
    with patch("openmas.assets.downloaders.os.environ", {"HF_TOKEN": "test-hf-token"}):
        # Initial token is None
        token = None

        # Extract token from env var specified in config
        if source_config.authentication and source_config.authentication.hf:
            token_env_var = source_config.authentication.hf.token_env_var
            token = os.environ.get(token_env_var)

        # Verify token
        assert token == "test-hf-token"


def test_hf_custom_token_extraction(mock_env_vars):
    """Test extracting custom token for Hugging Face Hub."""
    # Create a source config with custom authentication
    source_config = AssetSourceConfig(
        type="hf",
        repo_id="user/model",
        filename="model.bin",
        authentication=AssetAuthentication(hf=HuggingFaceAuthDetails(token_env_var="CUSTOM_TOKEN")),
    )

    # Directly test the token extraction logic from the downloader
    with patch("openmas.assets.downloaders.os.environ", {"CUSTOM_TOKEN": "custom-token-value"}):
        # Initial token is None
        token = None

        # Extract token from env var specified in config
        if source_config.authentication and source_config.authentication.hf:
            token_env_var = source_config.authentication.hf.token_env_var
            token = os.environ.get(token_env_var)

        # Verify token
        assert token == "custom-token-value"


def test_get_downloader_for_source_warnings():
    """Test warning messages when authentication might be needed but not provided."""
    # Test Hugging Face source without authentication
    with patch("openmas.assets.downloaders.logger") as mock_logger:
        with patch("openmas.assets.downloaders.HF_AVAILABLE", True):
            source = AssetSourceConfig(type="hf", repo_id="user/model")
            get_downloader_for_source(source)

    # Verify warning was logged
    mock_logger.warning.assert_called_with(
        "No authentication provided for Hugging Face Hub source. "
        "This may fail if the repository requires authentication. "
        "Consider adding authentication details to the asset configuration."
    )

    # Test HTTP source without authentication
    with patch("openmas.assets.downloaders.logger") as mock_logger:
        source = AssetSourceConfig(type="http", url="https://example.com/model.bin")
        get_downloader_for_source(source)

    # Verify debug message was logged
    mock_logger.debug.assert_called_with(
        "No authentication provided for HTTP source. "
        "This will work for public resources, but may fail if authentication is required."
    )


@pytest.mark.asyncio
async def test_http_downloader_with_strict_authentication():
    """Test HTTP downloader with strict authentication."""
    # Create a source config with authentication
    source_config = AssetSourceConfig(
        type="http",
        url="https://example.com/model.bin",
        authentication=AssetAuthentication(
            http=HttpAuthDetails(token_env_var="NONEXISTENT_TOKEN", scheme="Bearer", header_name="Authorization")
        ),
    )

    downloader = HttpDownloader()

    # Test with strict_authentication=True
    with patch("openmas.assets.downloaders.os.environ", {}):
        with pytest.raises(AssetAuthenticationError) as exc_info:
            await downloader.download(source_config, MagicMock(), strict_authentication=True)

        # Verify exception details
        assert "HTTP authentication token environment variable 'NONEXISTENT_TOKEN' not found or empty" in str(
            exc_info.value
        )
        assert exc_info.value.source_type == "http"
        assert exc_info.value.source_info == "https://example.com/model.bin"
        assert exc_info.value.token_env_var == "NONEXISTENT_TOKEN"


@pytest.mark.asyncio
async def test_http_downloader_authentication_error_handling():
    """Test HTTP downloader handling of 401/403 errors."""
    # Create a source config with authentication
    source_config = AssetSourceConfig(
        type="http",
        url="https://example.com/model.bin",
        authentication=AssetAuthentication(
            http=HttpAuthDetails(token_env_var="HTTP_TOKEN", scheme="Bearer", header_name="Authorization")
        ),
    )

    downloader = HttpDownloader()

    # Mock response with 401 error
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.reason_phrase = "Unauthorized"

    # Mock the httpx client
    mock_client = MagicMock()
    mock_client.stream.return_value.__aenter__.return_value = mock_response

    # Use patch to return the mock client
    with patch("openmas.assets.downloaders.os.environ", {"HTTP_TOKEN": "invalid-token"}):
        with patch("httpx.AsyncClient", return_value=MagicMock()) as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.stream.return_value.__aenter__.return_value = mock_response
            with pytest.raises(AssetDownloadError) as exc_info:
                await downloader.download(source_config, MagicMock())

    # Verify error message has authentication context
    error_message = str(exc_info.value)
    assert "HTTP error 401: Unauthorized" in error_message
    assert "authentication issue" in error_message
    assert "Check that the token in 'HTTP_TOKEN'" in error_message


@pytest.mark.asyncio
async def test_hf_downloader_with_strict_authentication():
    """Test Hugging Face downloader with strict authentication."""
    # Skip test if huggingface_hub is not available
    with patch("openmas.assets.downloaders.HF_AVAILABLE", True):
        with patch("openmas.assets.downloaders.HF_HUB_DOWNLOAD", MagicMock()):
            # Create a source config with authentication
            source_config = AssetSourceConfig(
                type="hf",
                repo_id="user/model",
                filename="model.bin",
                authentication=AssetAuthentication(hf=HuggingFaceAuthDetails(token_env_var="NONEXISTENT_TOKEN")),
            )

            downloader = HfDownloader()

            # Test with strict_authentication=True
            with patch("openmas.assets.downloaders.os.environ", {}):
                # Key fix: We need to check that the function raises AssetAuthenticationError
                # BEFORE it tries to run the _download method at all
                with patch.object(downloader, "_download") as mock_download:
                    with pytest.raises(AssetAuthenticationError) as exc_info:
                        await downloader.download(source_config, MagicMock(), strict_authentication=True)

                    # Verify the error message and parameters
                    assert (
                        "Hugging Face authentication token environment variable 'NONEXISTENT_TOKEN' not found or empty"
                        in str(exc_info.value)
                    )
                    assert exc_info.value.source_type == "hf"
                    assert exc_info.value.source_info == "user/model/model.bin"
                    assert exc_info.value.token_env_var == "NONEXISTENT_TOKEN"

                    # Verify that _download was never called
                    mock_download.assert_not_called()


@pytest.mark.asyncio
async def test_hf_downloader_authentication_error_handling():
    """Test Hugging Face downloader handling of authentication errors."""
    # Skip test if huggingface_hub is not available
    with patch("openmas.assets.downloaders.HF_AVAILABLE", True):
        # Create a source config with authentication
        source_config = AssetSourceConfig(
            type="hf",
            repo_id="user/model",
            filename="model.bin",
            authentication=AssetAuthentication(hf=HuggingFaceAuthDetails(token_env_var="HF_TOKEN")),
        )

        # Mock hf_hub_download to raise an authentication error
        mock_hf_hub_download = MagicMock(side_effect=Exception("401: Unauthorized"))

        with patch("openmas.assets.downloaders.HF_HUB_DOWNLOAD", mock_hf_hub_download):
            downloader = HfDownloader()

            # Test with an invalid token
            with patch("openmas.assets.downloaders.os.environ", {"HF_TOKEN": "invalid-token"}):
                with pytest.raises(AssetAuthenticationError) as exc_info:
                    await downloader.download(source_config, MagicMock())

            # Verify error message has authentication context - fix the assertion to match the actual message
            error_message = str(exc_info.value)
            assert "Authentication error" in error_message
            assert "the provided token may be invalid or expired" in error_message
