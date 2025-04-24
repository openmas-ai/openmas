"""Tests for the config module."""

import json
import os
from typing import Any, Dict
from unittest import mock

import pytest
from pydantic import Field
from pytest import MonkeyPatch

from simple_mas.config import AgentConfig, load_config
from simple_mas.exceptions import ConfigurationError


class TestAgentConfig:
    """Tests for the AgentConfig class."""

    def test_required_fields(self) -> None:
        """Test that the required fields are validated."""
        # Should succeed with just a name
        config = AgentConfig(name="test-agent")
        assert config.name == "test-agent"
        assert config.log_level == "INFO"
        assert config.service_urls == {}

        # Should fail without a name
        with pytest.raises(ValueError):
            AgentConfig()


class TestCustomConfig:
    """Tests for custom configurations."""

    class CustomConfig(AgentConfig):
        """A custom configuration class."""

        api_key: str = Field(..., description="API key for external service")
        model_name: str = Field("gpt-4", description="Model to use")

    def test_custom_config(self) -> None:
        """Test that custom configurations work."""
        config = self.CustomConfig(name="test-agent", api_key="abc123")
        assert config.name == "test-agent"
        assert config.log_level == "INFO"
        assert config.api_key == "abc123"
        assert config.model_name == "gpt-4"

        # Should fail without an API key
        with pytest.raises(ValueError):
            self.CustomConfig(name="test-agent")


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_from_env(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("AGENT_NAME", "test-agent")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        config = load_config(AgentConfig)
        assert config.name == "test-agent"
        assert config.log_level == "DEBUG"
        assert config.service_urls == {}

    def test_load_service_urls(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading service URLs from environment variables."""
        monkeypatch.setenv("AGENT_NAME", "test-agent")
        monkeypatch.setenv(
            "SERVICE_URLS", json.dumps({"chess-engine": "http://localhost:8000", "vision": "http://localhost:8001"})
        )

        config = load_config(AgentConfig)
        assert config.service_urls == {"chess-engine": "http://localhost:8000", "vision": "http://localhost:8001"}

    def test_load_individual_service_urls(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading individual service URLs from environment variables."""
        monkeypatch.setenv("AGENT_NAME", "test-agent")
        monkeypatch.setenv("SERVICE_URL_CHESS_ENGINE", "http://localhost:8000")
        monkeypatch.setenv("SERVICE_URL_VISION", "http://localhost:8001")

        config = load_config(AgentConfig)
        assert config.service_urls == {"chess_engine": "http://localhost:8000", "vision": "http://localhost:8001"}

    def test_json_config(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading configuration from a JSON string."""
        json_config: Dict[str, Any] = {
            "name": "test-agent",
            "log_level": "DEBUG",
            "service_urls": {"chess-engine": "http://localhost:8000"},
        }
        monkeypatch.setenv("CONFIG", json.dumps(json_config))

        config = load_config(AgentConfig)
        assert config.name == "test-agent"
        assert config.log_level == "DEBUG"
        assert config.service_urls == {"chess-engine": "http://localhost:8000"}

    def test_invalid_json(self, monkeypatch: MonkeyPatch) -> None:
        """Test that invalid JSON raises an error."""
        monkeypatch.setenv("CONFIG", "{invalid_json")

        with pytest.raises(ConfigurationError):
            load_config(AgentConfig)

    def test_invalid_service_urls(self, monkeypatch: MonkeyPatch) -> None:
        """Test that invalid service URLs JSON raises an error."""
        monkeypatch.setenv("AGENT_NAME", "test-agent")
        monkeypatch.setenv("SERVICE_URLS", "{invalid_json")

        with pytest.raises(ConfigurationError):
            load_config(AgentConfig)

    def test_prefix(self, monkeypatch: MonkeyPatch) -> None:
        """Test using a prefix for environment variables."""
        monkeypatch.setenv("APP_AGENT_NAME", "test-agent")
        monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")

        config = load_config(AgentConfig, prefix="APP")
        assert config.name == "test-agent"
        assert config.log_level == "DEBUG"

    def test_custom_config_from_env(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading a custom configuration from environment variables."""

        class CustomConfig(AgentConfig):
            api_key: str = Field(..., description="API key for external service")
            model_name: str = Field("gpt-4", description="Model to use")

        monkeypatch.setenv("AGENT_NAME", "test-agent")
        monkeypatch.setenv("CONFIG", json.dumps({"api_key": "abc123", "model_name": "llama-3"}))

        config = load_config(CustomConfig)
        assert config.name == "test-agent"
        assert config.api_key == "abc123"
        assert config.model_name == "llama-3"

    def test_missing_required_fields(self, monkeypatch: MonkeyPatch) -> None:
        """Test that missing required fields raise an error."""
        # No AGENT_NAME set
        with pytest.raises(ConfigurationError):
            load_config(AgentConfig)

        class CustomConfig(AgentConfig):
            api_key: str

        monkeypatch.setenv("AGENT_NAME", "test-agent")
        # No api_key set
        with pytest.raises(ConfigurationError):
            load_config(CustomConfig)


def test_load_config_extension_paths():
    """Test loading extension_paths from environment variables."""
    extension_paths = ["/path/to/extensions", "./local/extensions"]
    extension_paths_json = json.dumps(extension_paths)

    with mock.patch.dict(os.environ, {"EXTENSION_PATHS": extension_paths_json}):
        config = load_config(AgentConfig)
        assert config.extension_paths == extension_paths


def test_load_config_extension_paths_invalid_json():
    """Test handling invalid JSON in EXTENSION_PATHS."""
    with mock.patch.dict(os.environ, {"EXTENSION_PATHS": "not-json"}):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "Invalid JSON in EXTENSION_PATHS" in str(exc_info.value)


def test_load_config_extension_paths_not_list():
    """Test handling non-list value in EXTENSION_PATHS."""
    with mock.patch.dict(os.environ, {"EXTENSION_PATHS": '{"not": "list"}'}):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "EXTENSION_PATHS must be a JSON array" in str(exc_info.value)
