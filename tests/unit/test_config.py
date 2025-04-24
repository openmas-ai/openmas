"""Tests for the SimpleMas config module."""

import json
import os
from typing import Any, Dict
from unittest import mock
from unittest.mock import mock_open, patch

import pytest
import yaml
from pydantic import Field
from pytest import MonkeyPatch

from simple_mas.config import AgentConfig, _load_project_config, load_config
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

    with mock.patch.dict(os.environ, {"AGENT_NAME": "test-agent", "EXTENSION_PATHS": extension_paths_json}):
        config = load_config(AgentConfig)
        assert config.extension_paths == extension_paths


def test_load_config_extension_paths_invalid_json():
    """Test handling invalid JSON in EXTENSION_PATHS."""
    with mock.patch.dict(os.environ, {"AGENT_NAME": "test-agent", "EXTENSION_PATHS": "not-json"}):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "Invalid JSON in EXTENSION_PATHS" in str(exc_info.value)


def test_load_config_extension_paths_not_list():
    """Test handling non-list value in EXTENSION_PATHS."""
    with mock.patch.dict(os.environ, {"AGENT_NAME": "test-agent", "EXTENSION_PATHS": '{"not": "list"}'}):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "EXTENSION_PATHS must be a JSON array" in str(exc_info.value)


@pytest.fixture
def mock_project_config():
    """Create a mock project config."""
    return {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"agent1": "agents/agent1"},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions/custom"],
        "default_config": {"log_level": "DEBUG", "communicator_type": "http", "communicator_options": {"timeout": 30}},
    }


def test_load_project_config_from_env():
    """Test loading project config from environment variable."""
    mock_config = {"name": "env_project", "default_config": {"log_level": "DEBUG"}}

    with patch.dict(os.environ, {"SIMPLEMAS_PROJECT_CONFIG": yaml.dump(mock_config)}):
        config = _load_project_config()

        assert config["name"] == "env_project"
        assert config["default_config"]["log_level"] == "DEBUG"


def test_load_project_config_from_file(mock_project_config):
    """Test loading project config from file."""
    with patch.dict(os.environ, {}, clear=True), patch("pathlib.Path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=yaml.dump(mock_project_config))
    ):
        config = _load_project_config()

        assert config["name"] == "test_project"
        assert config["default_config"]["log_level"] == "DEBUG"
        assert config["default_config"]["communicator_type"] == "http"


def test_load_project_config_file_not_found():
    """Test loading project config when file is not found."""
    with patch.dict(os.environ, {}, clear=True), patch("pathlib.Path.exists", return_value=False):
        config = _load_project_config()

        assert config == {}


def test_load_project_config_invalid_yaml():
    """Test loading project config with invalid YAML."""
    with patch.dict(os.environ, {"SIMPLEMAS_PROJECT_CONFIG": "invalid: yaml: content:"}), patch(
        "yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML")
    ):
        config = _load_project_config()

        assert config == {}


def test_load_config_with_default_config(mock_project_config):
    """Test load_config with default config from project config."""
    with patch("simple_mas.config._load_project_config", return_value=mock_project_config), patch.dict(
        os.environ, {"AGENT_NAME": "test_agent"}
    ):
        config = load_config(AgentConfig)

        assert config.name == "test_agent"
        assert config.log_level == "DEBUG"  # From default_config
        assert config.communicator_type == "http"  # From default_config
        assert config.communicator_options["timeout"] == 30  # From default_config


def test_load_config_env_overrides_default(mock_project_config):
    """Test that environment variables override default config."""
    with patch("simple_mas.config._load_project_config", return_value=mock_project_config), patch.dict(
        os.environ,
        {
            "AGENT_NAME": "test_agent",
            "LOG_LEVEL": "INFO",  # Override default DEBUG
            "COMMUNICATOR_TYPE": "mcp_stdio",  # Override default http
        },
    ):
        config = load_config(AgentConfig)

        assert config.name == "test_agent"
        assert config.log_level == "INFO"  # From env, overriding default
        assert config.communicator_type == "mcp_stdio"  # From env, overriding default
        assert config.communicator_options["timeout"] == 30  # Still from default_config


def test_load_config_json_overrides_default(mock_project_config):
    """Test that JSON config overrides default config."""
    json_config = {
        "name": "json_agent",
        "log_level": "WARNING",
        "communicator_options": {"timeout": 60, "new_option": "value"},
    }

    with patch("simple_mas.config._load_project_config", return_value=mock_project_config), patch.dict(
        os.environ, {"CONFIG": json.dumps(json_config)}
    ):
        config = load_config(AgentConfig)

        assert config.name == "json_agent"  # From JSON
        assert config.log_level == "WARNING"  # From JSON, overriding default
        assert config.communicator_type == "http"  # From default_config
        assert config.communicator_options["timeout"] == 60  # From JSON, overriding default
        assert config.communicator_options["new_option"] == "value"  # From JSON


def test_load_config_extension_paths_merged(mock_project_config):
    """Test that extension paths from project config are merged with env config."""
    env_extension_paths = ["custom/path1", "custom/path2"]

    with patch("simple_mas.config._load_project_config", return_value=mock_project_config), patch.dict(
        os.environ, {"AGENT_NAME": "test_agent", "EXTENSION_PATHS": json.dumps(env_extension_paths)}
    ):
        config = load_config(AgentConfig)

        # Should contain both from env and from project config
        assert "custom/path1" in config.extension_paths
        assert "custom/path2" in config.extension_paths
        assert "extensions/custom" in config.extension_paths


def test_load_config_no_default_config():
    """Test load_config when there's no default config in project config."""
    project_config = {"name": "test_project", "version": "0.1.0", "agents": {}}

    with patch("simple_mas.config._load_project_config", return_value=project_config), patch.dict(
        os.environ, {"AGENT_NAME": "test_agent"}
    ):
        config = load_config(AgentConfig)

        assert config.name == "test_agent"
        assert config.log_level == "INFO"  # Model default
        assert config.communicator_type == "http"  # Model default


def test_load_config_validation_error():
    """Test load_config with validation error."""
    with patch("simple_mas.config._load_project_config", return_value={}), patch.dict(
        os.environ, {}
    ):  # Missing required 'name' field
        with pytest.raises(ConfigurationError, match="Configuration validation failed"):
            load_config(AgentConfig)


def test_load_config_with_individual_service_urls(mock_project_config):
    """Test load_config with individual service URLs."""
    with patch("simple_mas.config._load_project_config", return_value=mock_project_config), patch.dict(
        os.environ,
        {"AGENT_NAME": "test_agent", "SERVICE_URL_API": "http://api:8000", "SERVICE_URL_DATABASE": "http://db:5432"},
    ):
        config = load_config(AgentConfig)

        assert config.service_urls["api"] == "http://api:8000"
        assert config.service_urls["database"] == "http://db:5432"


def test_load_config_with_individual_communicator_options(mock_project_config):
    """Test load_config with individual communicator options."""
    with patch("simple_mas.config._load_project_config", return_value=mock_project_config), patch.dict(
        os.environ,
        {"AGENT_NAME": "test_agent", "COMMUNICATOR_OPTION_RETRY": "true", "COMMUNICATOR_OPTION_MAX_RETRIES": "5"},
    ):
        config = load_config(AgentConfig)

        # From default_config
        assert config.communicator_options["timeout"] == 30

        # From individual options
        assert config.communicator_options["retry"] is True
        assert config.communicator_options["max_retries"] == 5
