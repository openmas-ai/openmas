"""Tests for the asset authentication configuration models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from openmas.assets.config import (
    AssetAuthentication,
    AssetAuthStrategy,
    AssetConfig,
    AssetSourceConfig,
    HttpAuthDetails,
    HuggingFaceAuthDetails,
)


def test_http_auth_details_creation():
    """Test creating HttpAuthDetails with various configurations."""
    # Minimal configuration (only token_env_var is required)
    auth = HttpAuthDetails(token_env_var="MY_API_KEY")
    assert auth.token_env_var == "MY_API_KEY"
    assert auth.header_name == "Authorization"  # Default
    assert auth.scheme == "Bearer"  # Default

    # Custom configuration
    auth = HttpAuthDetails(token_env_var="CUSTOM_TOKEN", header_name="X-API-Key", scheme="")
    assert auth.token_env_var == "CUSTOM_TOKEN"
    assert auth.header_name == "X-API-Key"
    assert auth.scheme == ""  # Empty string for no scheme


def test_huggingface_auth_details_creation():
    """Test creating HuggingFaceAuthDetails with various configurations."""
    # Default configuration
    auth = HuggingFaceAuthDetails()
    assert auth.token_env_var == "HUGGINGFACE_TOKEN"  # Default

    # Custom configuration
    auth = HuggingFaceAuthDetails(token_env_var="CUSTOM_HF_TOKEN")
    assert auth.token_env_var == "CUSTOM_HF_TOKEN"


def test_asset_authentication_creation():
    """Test creating AssetAuthentication with various configurations."""
    # HTTP authentication
    auth = AssetAuthentication(strategy=AssetAuthStrategy.ENV_TOKEN, http=HttpAuthDetails(token_env_var="MY_API_KEY"))
    assert auth.strategy == AssetAuthStrategy.ENV_TOKEN
    assert auth.http is not None
    assert auth.http.token_env_var == "MY_API_KEY"
    assert auth.hf is None

    # Hugging Face authentication
    auth = AssetAuthentication(
        strategy=AssetAuthStrategy.ENV_TOKEN, hf=HuggingFaceAuthDetails(token_env_var="CUSTOM_HF_TOKEN")
    )
    assert auth.strategy == AssetAuthStrategy.ENV_TOKEN
    assert auth.hf is not None
    assert auth.hf.token_env_var == "CUSTOM_HF_TOKEN"
    assert auth.http is None

    # Multiple authentication types (valid, but only one will be used based on source type)
    auth = AssetAuthentication(
        strategy=AssetAuthStrategy.ENV_TOKEN,
        http=HttpAuthDetails(token_env_var="MY_API_KEY"),
        hf=HuggingFaceAuthDetails(token_env_var="CUSTOM_HF_TOKEN"),
    )
    assert auth.http is not None
    assert auth.hf is not None


def test_asset_source_config_with_auth():
    """Test creating AssetSourceConfig with authentication."""
    # HTTP source with authentication
    source = AssetSourceConfig(
        type="http",
        url="https://example.com/model.bin",
        authentication=AssetAuthentication(http=HttpAuthDetails(token_env_var="HTTP_TOKEN")),
    )
    assert source.type == "http"
    assert source.url == "https://example.com/model.bin"
    assert source.authentication is not None
    assert source.authentication.http is not None
    assert source.authentication.http.token_env_var == "HTTP_TOKEN"

    # Hugging Face source with authentication
    source = AssetSourceConfig(
        type="hf",
        repo_id="user/model",
        authentication=AssetAuthentication(hf=HuggingFaceAuthDetails(token_env_var="HF_TOKEN")),
    )
    assert source.type == "hf"
    assert source.repo_id == "user/model"
    assert source.authentication is not None
    assert source.authentication.hf is not None
    assert source.authentication.hf.token_env_var == "HF_TOKEN"


def test_asset_source_config_validation_errors():
    """Test validation errors in AssetSourceConfig."""
    # Missing HTTP auth details when authentication is specified for HTTP source
    with pytest.raises(ValidationError, match="HTTP authentication details must be provided"):
        AssetSourceConfig(
            type="http",
            url="https://example.com/model.bin",
            authentication=AssetAuthentication(
                # Missing http field
                hf=HuggingFaceAuthDetails(token_env_var="HF_TOKEN")
            ),
        )

    # Missing HF auth details when authentication is specified for HF source
    with pytest.raises(ValidationError, match="Hugging Face authentication details must be provided"):
        AssetSourceConfig(
            type="hf",
            repo_id="user/model",
            authentication=AssetAuthentication(
                # Missing hf field
                http=HttpAuthDetails(token_env_var="HTTP_TOKEN")
            ),
        )

    # Authentication not applicable for local source
    with pytest.raises(ValidationError, match="Authentication is not applicable for local source type"):
        AssetSourceConfig(
            type="local",
            path=Path("/path/to/file"),
            authentication=AssetAuthentication(http=HttpAuthDetails(token_env_var="TOKEN")),
        )


def test_asset_config_with_authentication():
    """Test creating a full AssetConfig with authentication."""
    # Create an asset config with HTTP authentication
    asset = AssetConfig(
        name="test-asset",
        source=AssetSourceConfig(
            type="http",
            url="https://example.com/model.bin",
            authentication=AssetAuthentication(
                http=HttpAuthDetails(token_env_var="MY_API_KEY", scheme="Bearer", header_name="Authorization")
            ),
        ),
        checksum="sha256:1234567890abcdef",
    )

    assert asset.name == "test-asset"
    assert asset.source.type == "http"
    assert asset.source.authentication is not None
    assert asset.source.authentication.http is not None
    assert asset.source.authentication.http.token_env_var == "MY_API_KEY"

    # Create an asset config with Hugging Face authentication
    asset = AssetConfig(
        name="hf-asset",
        source=AssetSourceConfig(
            type="hf",
            repo_id="user/model",
            filename="model.bin",
            authentication=AssetAuthentication(hf=HuggingFaceAuthDetails(token_env_var="MY_HF_TOKEN")),
        ),
    )

    assert asset.name == "hf-asset"
    assert asset.source.type == "hf"
    assert asset.source.authentication is not None
    assert asset.source.authentication.hf is not None
    assert asset.source.authentication.hf.token_env_var == "MY_HF_TOKEN"
