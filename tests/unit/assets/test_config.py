"""Tests for the OpenMAS asset configuration module."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from openmas.assets.config import AssetConfig, AssetSettings, AssetSourceConfig


class TestAssetSourceConfig:
    """Tests for the AssetSourceConfig class."""

    def test_http_source_valid(self) -> None:
        """Test creating a valid HTTP source configuration."""
        source = AssetSourceConfig(type="http", url="https://example.com/model.bin")
        assert source.type == "http"
        assert source.url == "https://example.com/model.bin"
        assert source.repo_id is None
        assert source.path is None

    def test_http_source_invalid_missing_url(self) -> None:
        """Test that HTTP source without URL raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AssetSourceConfig(type="http")
        assert "URL is required for HTTP source type" in str(exc_info.value)

    def test_hf_source_valid(self) -> None:
        """Test creating a valid Hugging Face source configuration."""
        source = AssetSourceConfig(
            type="hf", repo_id="openai/whisper-tiny", filename="pytorch_model.bin", revision="main"
        )
        assert source.type == "hf"
        assert source.repo_id == "openai/whisper-tiny"
        assert source.filename == "pytorch_model.bin"
        assert source.revision == "main"
        assert source.url is None
        assert source.path is None

    def test_hf_source_invalid_missing_repo_id(self) -> None:
        """Test that HF source without repo_id raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AssetSourceConfig(type="hf")
        assert "repo_id is required for Hugging Face source type" in str(exc_info.value)

    def test_local_source_valid(self) -> None:
        """Test creating a valid local source configuration."""
        source = AssetSourceConfig(type="local", path=Path("/path/to/model.bin"))
        assert source.type == "local"
        assert source.path == Path("/path/to/model.bin")
        assert source.url is None
        assert source.repo_id is None

    def test_local_source_invalid_missing_path(self) -> None:
        """Test that local source without path raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AssetSourceConfig(type="local")
        assert "path is required for local source type" in str(exc_info.value)


class TestAssetConfig:
    """Tests for the AssetConfig class."""

    def test_minimal_asset_config(self) -> None:
        """Test creating a minimal valid asset configuration."""
        asset = AssetConfig(
            name="gpt-model",
            source=AssetSourceConfig(type="http", url="https://example.com/model.bin"),
        )
        assert asset.name == "gpt-model"
        assert asset.version == "latest"
        assert asset.asset_type == "model"
        assert asset.source.type == "http"
        assert asset.source.url == "https://example.com/model.bin"
        assert asset.checksum is None
        assert asset.unpack is False
        assert asset.unpack_format is None
        assert asset.description is None

    def test_full_asset_config(self) -> None:
        """Test creating a complete asset configuration."""
        asset = AssetConfig(
            name="whisper-tiny",
            version="1.0.0",
            asset_type="speech-model",
            source=AssetSourceConfig(
                type="hf",
                repo_id="openai/whisper-tiny",
                filename="pytorch_model.bin",
                revision="main",
            ),
            checksum="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            unpack=True,
            unpack_format="tar.gz",
            description="Whisper speech recognition model (tiny variant)",
        )
        assert asset.name == "whisper-tiny"
        assert asset.version == "1.0.0"
        assert asset.asset_type == "speech-model"
        assert asset.source.type == "hf"
        assert asset.source.repo_id == "openai/whisper-tiny"
        assert asset.checksum == "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        assert asset.unpack is True
        assert asset.unpack_format == "tar.gz"
        assert asset.description == "Whisper speech recognition model (tiny variant)"

    def test_invalid_checksum_format(self) -> None:
        """Test that invalid checksum format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AssetConfig(
                name="gpt-model",
                source=AssetSourceConfig(type="http", url="https://example.com/model.bin"),
                checksum="md5:1234567890abcdef1234567890abcdef",
            )
        assert "Checksum must be in format 'sha256:<hex_digest>'" in str(exc_info.value)

    def test_unpack_without_format(self) -> None:
        """Test that unpack=True without unpack_format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            AssetConfig(
                name="gpt-model",
                source=AssetSourceConfig(type="http", url="https://example.com/model.bin"),
                unpack=True,
            )
        assert "unpack_format is required when unpack is True" in str(exc_info.value)


class TestAssetSettings:
    """Tests for the AssetSettings class."""

    def test_default_settings(self) -> None:
        """Test creating asset settings with defaults."""
        settings = AssetSettings()
        assert settings.cache_dir is None

    def test_custom_cache_dir(self) -> None:
        """Test creating asset settings with custom cache directory."""
        settings = AssetSettings(cache_dir=Path("/custom/cache/dir"))
        assert settings.cache_dir == Path("/custom/cache/dir")
