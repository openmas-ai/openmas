"""Tests for the OpenMAS config module."""

import json
import os
from pathlib import Path
from typing import Any, Dict, cast
from unittest import mock

# Using only the needed imports
from unittest.mock import mock_open, patch

import pytest
import yaml
from pydantic import Field, ValidationError
from pytest import MonkeyPatch

from openmas.config import (
    AgentConfig,
    ProjectConfig,
    _coerce_env_value,
    _deep_merge_dicts,
    _get_env_var_with_type,
    _load_environment_config_files,
    _load_project_config,
    _load_yaml_config,
    load_config,
)
from openmas.exceptions import ConfigurationError


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
        with pytest.raises(ValidationError):
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
        with pytest.raises(ValidationError):
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
        # Ensure there's no AGENT_NAME set to override the json config's name
        monkeypatch.delenv("AGENT_NAME", raising=False)

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
        # Clear environment variables
        monkeypatch.delenv("AGENT_NAME", raising=False)
        monkeypatch.delenv("CONFIG", raising=False)

        # Patch _load_project_config to return empty config
        with patch("openmas.config._load_project_config", return_value={}):
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
    extension_paths = ["/path/to/extensions", "./local/extensions/"]
    extension_paths_json = json.dumps(extension_paths)

    # Mock the project config to ensure we have a valid config with all required fields
    mock_project_data = {"name": "test-project", "version": "0.1.0", "agents": {"agent1": "agents/agent1"}}

    with (
        patch("openmas.config._load_project_config", return_value=mock_project_data),
        mock.patch.dict(os.environ, {"AGENT_NAME": "test-agent", "EXTENSION_PATHS": extension_paths_json}),
    ):
        config = load_config(AgentConfig)
        assert config.extension_paths == extension_paths


def test_load_config_extension_paths_invalid_json():
    """Test handling invalid JSON in EXTENSION_PATHS."""
    # Mock the project config to ensure we have a valid config with all required fields
    mock_project_data = {"name": "test-project", "version": "0.1.0", "agents": {"agent1": "agents/agent1"}}

    with (
        patch("openmas.config._load_project_config", return_value=mock_project_data),
        mock.patch.dict(os.environ, {"AGENT_NAME": "test-agent", "EXTENSION_PATHS": "not-json"}),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "Invalid JSON in EXTENSION_PATHS" in str(exc_info.value)


def test_load_config_extension_paths_not_list():
    """Test handling non-list value in EXTENSION_PATHS."""
    # Mock the project config to ensure we have a valid config with all required fields
    mock_project_data = {"name": "test-project", "version": "0.1.0", "agents": {"agent1": "agents/agent1"}}

    with (
        patch("openmas.config._load_project_config", return_value=mock_project_data),
        mock.patch.dict(os.environ, {"AGENT_NAME": "test-agent", "EXTENSION_PATHS": '{"not": "list"}'}),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "EXTENSION_PATHS must be a JSON array" in str(exc_info.value)


@pytest.fixture
def mock_project_config():
    """Create a mock project config."""
    return {
        "name": "test_project",
        "version": "0.1.0",
        "agents": {"agent1": {"module": "agents.agent1", "class": "Agent1"}},
        "shared_paths": ["shared"],
        "extension_paths": ["extensions/custom"],
        "default_config": {"log_level": "DEBUG", "communicator_type": "http", "communicator_options": {"timeout": 30}},
    }


def test_load_project_config_from_env():
    """Test loading project config from environment variable."""
    # Make sure we include all required fields
    mock_config = {
        "name": "env_project",
        "version": "0.1.0",
        "agents": {"agent1": "agents/agent1"},
        "default_config": {"log_level": "DEBUG"},
    }

    with patch.dict(os.environ, {"OPENMAS_PROJECT_CONFIG": yaml.dump(mock_config)}):
        config = _load_project_config()

        assert config["name"] == "env_project"
        assert config["default_config"]["log_level"] == "DEBUG"


def test_load_project_config_from_file(mock_project_config):
    """Test loading project config from file."""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=yaml.dump(mock_project_config))),
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
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="invalid: yaml: content:")),
        patch("yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML")),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            _load_project_config()
        assert "Error in project config file" in str(exc_info.value)


def test_load_config_with_default_config(mock_project_config):
    """Test load_config with default config from project config."""
    with (
        patch("openmas.config._load_project_config", return_value=mock_project_config),
        patch.dict(os.environ, {"AGENT_NAME": "test_agent"}),
    ):
        config = load_config(AgentConfig)

        assert config.name == "test_agent"
        assert config.log_level == "DEBUG"  # From default_config
        assert config.communicator_type == "http"  # From default_config
        assert config.communicator_options["timeout"] == 30  # From default_config


def test_load_config_env_overrides_default(mock_project_config):
    """Test that environment variables override default config."""
    with (
        patch("openmas.config._load_project_config", return_value=mock_project_config),
        patch.dict(
            os.environ,
            {
                "AGENT_NAME": "test_agent",
                "LOG_LEVEL": "INFO",  # Override default DEBUG
                "COMMUNICATOR_TYPE": "mcp_stdio",  # Override default http
            },
        ),
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

    with (
        patch("openmas.config._load_project_config", return_value=mock_project_config),
        patch.dict(os.environ, {"CONFIG": json.dumps(json_config)}, clear=True),
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

    with (
        patch("openmas.config._load_project_config", return_value=mock_project_config),
        patch.dict(os.environ, {"AGENT_NAME": "test_agent", "EXTENSION_PATHS": json.dumps(env_extension_paths)}),
    ):
        config = load_config(AgentConfig)

        # Should contain both from env and from project config
        assert "custom/path1" in config.extension_paths
        assert "custom/path2" in config.extension_paths
        assert "extensions/custom" in config.extension_paths


def test_load_config_no_default_config():
    """Test load_config when there's no default config in project config."""
    project_config = {"name": "test_project", "version": "0.1.0", "agents": {}}

    with (
        patch("openmas.config._load_project_config", return_value=project_config),
        patch.dict(os.environ, {"AGENT_NAME": "test_agent"}),
    ):
        config = load_config(AgentConfig)

        assert config.name == "test_agent"
        assert config.log_level == "INFO"  # Model default
        assert config.communicator_type == "http"  # Model default


def test_load_config_validation_error():
    """Test load_config with validation error."""

    # Create a class with a required field that isn't being provided
    class CustomConfigWithRequiredField(AgentConfig):
        required_field: str  # Required field not provided in config

    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent"}, clear=True),
    ):
        with pytest.raises(ConfigurationError, match="Configuration validation failed"):
            load_config(CustomConfigWithRequiredField)


def test_load_config_with_individual_service_urls(mock_project_config):
    """Test load_config with individual service URLs."""
    with (
        patch("openmas.config._load_project_config", return_value=mock_project_config),
        patch.dict(
            os.environ,
            {
                "AGENT_NAME": "test_agent",
                "SERVICE_URL_API": "http://api:8000",
                "SERVICE_URL_DATABASE": "http://db:5432",
            },
        ),
    ):
        config = load_config(AgentConfig)

        assert config.service_urls["api"] == "http://api:8000"
        assert config.service_urls["database"] == "http://db:5432"


def test_load_config_with_individual_communicator_options(mock_project_config):
    """Test load_config with individual communicator options."""
    with (
        patch("openmas.config._load_project_config", return_value=mock_project_config),
        patch.dict(
            os.environ,
            {"AGENT_NAME": "test_agent", "COMMUNICATOR_OPTION_RETRY": "true", "COMMUNICATOR_OPTION_MAX_RETRIES": "5"},
        ),
    ):
        config = load_config(AgentConfig)

        # From default_config
        assert config.communicator_options["timeout"] == 30

        # From individual options
        assert config.communicator_options["retry"] is True
        assert config.communicator_options["max_retries"] == 5


def test_find_project_root():
    """Test finding the project root by checking for openmas_project.yml."""
    from openmas.config import _find_project_root

    # Mock the current working directory
    cwd_mock = Path("/some/project/directory")

    # Mock Path.cwd() to return our test path
    with patch("pathlib.Path.cwd", return_value=cwd_mock):
        # Case 1: Project file exists in the current directory
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            result = _find_project_root()
            assert result == cwd_mock

        # Case 2: Project file doesn't exist in current directory or any parent directories
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            result = _find_project_root()
            assert result is None

    # Test with explicit directory
    explicit_dir = Path("/explicit/directory")
    with patch("pathlib.Path.resolve", return_value=explicit_dir), patch("pathlib.Path.exists", return_value=True):
        result = _find_project_root(explicit_dir)
        assert result == explicit_dir


def test_find_project_root_explicit_dir():
    """Test finding the project root with an explicitly provided directory path."""
    from openmas.config import _find_project_root

    # Case 1: Explicit project directory with openmas_project.yml
    with (
        patch("pathlib.Path.resolve", return_value=Path("/explicit/path")),
        patch("pathlib.Path.__truediv__", return_value=Path("/explicit/path/openmas_project.yml")),
        patch("pathlib.Path.exists", return_value=True),
    ):
        result = _find_project_root(Path("/explicit/path"))
        assert result == Path("/explicit/path")

    # Case 2: Explicit project directory without openmas_project.yml
    with (
        patch("pathlib.Path.resolve", return_value=Path("/explicit/path")),
        patch("pathlib.Path.__truediv__", return_value=Path("/explicit/path/openmas_project.yml")),
        patch("pathlib.Path.exists", return_value=False),
    ):
        result = _find_project_root(Path("/explicit/path"))
        assert result is None


def test_find_project_root_current_dir():
    """Test finding the project root in the current directory."""
    from openmas.config import _find_project_root

    # Use a different approach that doesn't try to patch exists on a PosixPath
    with patch("pathlib.Path.cwd", return_value=Path("/current/dir")), patch("pathlib.Path.exists", return_value=True):
        result = _find_project_root()
        assert result == Path("/current/dir")


def test_find_project_root_parent_dir():
    """Test finding a project root in a parent directory."""
    from openmas.config import _find_project_root

    # Mock the directory paths
    mock_cwd = mock.MagicMock(spec=Path)
    mock_parent = mock.MagicMock(spec=Path)
    mock_grandparent = mock.MagicMock(spec=Path)

    # Setup the necessary Path mocks
    with mock.patch("pathlib.Path.cwd", return_value=mock_cwd):
        # Configure the parent directory chain
        mock_cwd.parent = mock_parent
        mock_parent.parent = mock_grandparent

        # Configure exists() calls
        mock_cwd_config = mock.MagicMock()
        mock_parent_config = mock.MagicMock()
        mock_grandparent_config = mock.MagicMock()

        mock_cwd.__truediv__.return_value = mock_cwd_config
        mock_parent.__truediv__.return_value = mock_parent_config
        mock_grandparent.__truediv__.return_value = mock_grandparent_config

        mock_cwd_config.exists.return_value = False
        mock_parent_config.exists.return_value = False
        mock_grandparent_config.exists.return_value = True

        # Call the function
        result = _find_project_root()

        # Verify it returns the grandparent dir where the config file was found
        assert result == mock_grandparent


def test_load_yaml_config():
    """Test loading a YAML configuration file."""
    test_config: Dict[str, Any] = {"name": "test", "log_level": "DEBUG"}

    # Test successful load
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=yaml.dump(test_config))),
    ):
        config = _load_yaml_config(Path("/config/test.yml"))
        assert config["name"] == "test"
        assert config["log_level"] == "DEBUG"

    # Test file not found
    with patch("pathlib.Path.exists", return_value=False):
        config = _load_yaml_config(Path("/config/missing.yml"))
        assert config == {}

    # Test invalid YAML
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="invalid: yaml: content:")),
        patch("yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML")),
    ):
        with pytest.raises(ConfigurationError):
            _load_yaml_config(Path("/config/invalid.yml"))


def test_deep_merge_dicts():
    """Test deep merging of dictionaries."""
    # Basic merge
    base: Dict[str, Any] = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
    override: Dict[str, Any] = {"b": 5, "c": {"e": 6, "f": 7}, "g": 8}

    result = _deep_merge_dicts(base, override)
    assert result["a"] == 1
    assert result["b"] == 5
    assert result["c"]["d"] == 3
    assert result["c"]["e"] == 6
    assert result["c"]["f"] == 7
    assert result["g"] == 8

    # Ensure original dicts are not modified
    assert base["b"] == 2
    assert base["c"]["e"] == 4
    assert "g" not in base


def test_load_environment_config_files():
    """Test loading configuration from environment-specific YAML files."""
    default_config: Dict[str, Any] = {"log_level": "INFO", "service_urls": {"service1": "http://default"}}
    env_config: Dict[str, Any] = {"log_level": "DEBUG", "service_urls": {"service2": "http://env"}}

    # Test loading both default and env configs
    with (
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "openmas.config._load_yaml_config",
            side_effect=lambda p: default_config if p.name == "default.yml" else env_config,
        ),
        patch.dict(os.environ, {"OPENMAS_ENV": "dev"}),
    ):
        config = cast(Dict[str, Any], _load_environment_config_files())
        assert config["log_level"] == "DEBUG"  # From env config
        assert config["service_urls"]["service1"] == "http://default"  # From default config
        assert config["service_urls"]["service2"] == "http://env"  # From env config

    # Test loading only default config (no OPENMAS_ENV)
    with (
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=True),
        patch("openmas.config._load_yaml_config", return_value=default_config),
        patch.dict(os.environ, {}, clear=True),
    ):
        config = cast(Dict[str, Any], _load_environment_config_files())
        assert config["log_level"] == "INFO"
        assert config["service_urls"]["service1"] == "http://default"

    # Test no project root found
    with patch("openmas.config._find_project_root", return_value=None):
        config = _load_environment_config_files()
        assert config == {}


def test_load_config_env_overrides_yaml():
    """Test that environment variables override YAML configuration."""
    # Create a simpler, more focused test that verifies env vars override YAML settings

    # Save original environment
    saved_environ = os.environ.copy()

    try:
        # Clear and set specific test environment
        os.environ.clear()
        os.environ["AGENT_NAME"] = "from-env-var"

        # Mock just what we need - YAML config with a name value that should be overridden
        yaml_config = {"name": "from-yaml", "communicator_type": "mcp"}

        with (
            patch("openmas.config._load_project_config", return_value={}),
            patch("openmas.config._load_environment_config_files", return_value=yaml_config),
        ):
            # Load config and verify env var overrides YAML
            config = load_config(AgentConfig)
            assert config.name == "from-env-var"  # Environment variable overrides
            assert config.communicator_type == "mcp"  # YAML value is used when no env var

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(saved_environ)


def test_load_config_with_service_urls_in_yaml():
    """Test loading service URLs from YAML files."""
    yaml_config: Dict[str, Any] = {
        "service_urls": {"service1": "http://service1.example.com", "service2": "http://service2.example.com"}
    }

    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch("openmas.config._load_environment_config_files", return_value=yaml_config),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent"}),
    ):
        config = load_config(AgentConfig)
        assert config.service_urls["service1"] == "http://service1.example.com"
        assert config.service_urls["service2"] == "http://service2.example.com"

    # Test env vars override YAML config
    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch("openmas.config._load_environment_config_files", return_value=yaml_config),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent", "SERVICE_URL_SERVICE1": "http://override.example.com"}),
    ):
        config = load_config(AgentConfig)
        assert config.service_urls["service1"] == "http://override.example.com"
        assert config.service_urls["service2"] == "http://service2.example.com"


def test_load_config_with_communicator_options_in_yaml():
    """Test loading communicator options from YAML files."""
    yaml_config: Dict[str, Any] = {"communicator_options": {"timeout": 30, "retries": 3}}

    # Test with YAML config only
    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch("openmas.config._load_environment_config_files", return_value=yaml_config),
    ):
        os.environ["AGENT_NAME"] = "test-agent"
        try:
            config = load_config(AgentConfig)
            assert config.communicator_options["timeout"] == 30
            assert config.communicator_options["retries"] == 3
        finally:
            if "AGENT_NAME" in os.environ:
                del os.environ["AGENT_NAME"]

    # Test env vars override YAML config while preserving keys not in env var
    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch("openmas.config._load_environment_config_files", return_value=yaml_config),
    ):
        os.environ["AGENT_NAME"] = "test-agent"
        os.environ["COMMUNICATOR_OPTIONS"] = '{"timeout": 60, "max_connections": 10}'
        try:
            config = load_config(AgentConfig)
            # Now that we've implemented _deep_merge_dicts for communicator_options
            # we expect these assertions to pass
            assert config.communicator_options["timeout"] == 60  # Overridden
            assert config.communicator_options["retries"] == 3  # Still here from YAML
            assert config.communicator_options["max_connections"] == 10  # New from env
        finally:
            if "AGENT_NAME" in os.environ:
                del os.environ["AGENT_NAME"]
            if "COMMUNICATOR_OPTIONS" in os.environ:
                del os.environ["COMMUNICATOR_OPTIONS"]


def test_load_config_full_precedence_chain():
    """Test the full precedence chain with all configuration sources."""
    # 1. SDK Default (in AgentConfig)
    # 2. Project default_config
    project_config: Dict[str, Any] = {
        "default_config": {"log_level": "INFO", "communicator_type": "http", "communicator_options": {"timeout": 10}}
    }

    # 3. config/default.yml
    # 4. config/<env>.yml
    yaml_config: Dict[str, Any] = {
        "log_level": "DEBUG",
        "communicator_type": "mcp",
        "communicator_options": {"timeout": 30, "retries": 3},
        "service_urls": {"service1": "http://yaml.example.com"},
    }

    # 5. Environment variables (highest precedence)
    env_vars = {"AGENT_NAME": "test-agent", "LOG_LEVEL": "TRACE", "SERVICE_URL_SERVICE2": "http://env.example.com"}

    with (
        patch("openmas.config._load_project_config", return_value=project_config),
        patch("openmas.config._load_environment_config_files", return_value=yaml_config),
        patch.dict(os.environ, env_vars),
    ):
        config = load_config(AgentConfig)

        # From env vars (highest precedence)
        assert config.name == "test-agent"
        assert config.log_level == "TRACE"

        # Mixed service_urls (YAML + env vars)
        assert config.service_urls["service1"] == "http://yaml.example.com"
        assert config.service_urls["service2"] == "http://env.example.com"

        # From YAML (overrides project default_config)
        assert config.communicator_type == "mcp"
        assert config.communicator_options["timeout"] == 30
        assert config.communicator_options["retries"] == 3


def test_coerce_env_value():
    """Test converting environment variable strings to appropriate types."""
    # Boolean values
    assert _coerce_env_value("true", bool) is True
    assert _coerce_env_value("True", bool) is True
    assert _coerce_env_value("TRUE", bool) is True
    assert _coerce_env_value("yes", bool) is True
    assert _coerce_env_value("1", bool) is True
    assert _coerce_env_value("y", bool) is True

    assert _coerce_env_value("false", bool) is False
    assert _coerce_env_value("False", bool) is False
    assert _coerce_env_value("FALSE", bool) is False
    assert _coerce_env_value("no", bool) is False
    assert _coerce_env_value("0", bool) is False
    assert _coerce_env_value("n", bool) is False

    with pytest.raises(ValueError):
        _coerce_env_value("invalid", bool)

    # Integer values
    assert _coerce_env_value("123", int) == 123
    assert _coerce_env_value("-456", int) == -456

    with pytest.raises(ValueError):
        _coerce_env_value("12.34", int)

    # Float values
    assert _coerce_env_value("12.34", float) == 12.34
    assert _coerce_env_value("-56.78", float) == -56.78
    assert _coerce_env_value("90", float) == 90.0

    # String values (passed through)
    assert _coerce_env_value("hello", str) == "hello"


def test_get_env_var_with_type(monkeypatch):
    """Test getting environment variables with type conversion."""
    monkeypatch.setenv("TEST_INT", "123")
    monkeypatch.setenv("TEST_FLOAT", "45.67")
    monkeypatch.setenv("TEST_BOOL", "true")
    monkeypatch.setenv("TEST_STR", "hello world")
    monkeypatch.setenv("PREFIX_VALUE", "prefixed")

    # Test different types
    assert _get_env_var_with_type("TEST_INT", int) == 123
    assert _get_env_var_with_type("TEST_FLOAT", float) == 45.67
    assert _get_env_var_with_type("TEST_BOOL", bool) is True
    assert _get_env_var_with_type("TEST_STR", str) == "hello world"

    # Test with prefix
    assert _get_env_var_with_type("VALUE", str, prefix="PREFIX") == "prefixed"

    # Test non-existent variable
    assert _get_env_var_with_type("NONEXISTENT", str) is None

    # Test invalid value for type
    monkeypatch.setenv("TEST_INVALID_INT", "not-an-int")
    with pytest.raises(ConfigurationError):
        _get_env_var_with_type("TEST_INVALID_INT", int)


def test_load_yaml_config_missing_file():
    """Test loading a YAML configuration file that does not exist."""
    with patch("pathlib.Path.exists", return_value=False):
        config = _load_yaml_config(Path("/config/missing.yml"))
        assert config == {}


def test_load_yaml_config_none_or_not_dict():
    """Test loading a YAML configuration file that does not contain a dictionary."""
    # Test with None result from yaml.safe_load
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="")),
        patch("yaml.safe_load", return_value=None),
    ):
        config = _load_yaml_config(Path("/config/empty.yml"))
        assert config == {}

    # Test with non-dictionary result from yaml.safe_load
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="- list item")),
        patch("yaml.safe_load", return_value=["list item"]),
    ):
        config = _load_yaml_config(Path("/config/list.yml"))
        assert config == {}


def test_load_yaml_config_yaml_error():
    """Test loading a YAML configuration file with invalid YAML."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="invalid: : yaml")),
        patch("yaml.safe_load", side_effect=yaml.YAMLError("YAML syntax error")),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            _load_yaml_config(Path("/config/invalid.yml"))
        assert "Failed to parse YAML" in str(exc_info.value)
        assert "YAML syntax error" in str(exc_info.value)


def test_load_project_config_yaml_error():
    """Test loading a project configuration file with invalid YAML."""
    with (
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="invalid: : yaml")),
        patch("yaml.safe_load", side_effect=yaml.YAMLError("YAML syntax error")),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            _load_project_config()
        assert "Error in project config file" in str(exc_info.value)
        assert "YAML syntax error" in str(exc_info.value)


def test_load_project_config_from_env_yaml_error():
    """Test loading project config from environment variable with invalid YAML."""
    with (
        patch.dict(os.environ, {"OPENMAS_PROJECT_CONFIG": "invalid: : yaml"}),
        patch("yaml.safe_load", side_effect=yaml.YAMLError("YAML syntax error")),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            _load_project_config()
        assert "Failed to parse YAML in OPENMAS_PROJECT_CONFIG" in str(exc_info.value)


def test_load_environment_config_files_missing_config_dir():
    """Test loading environment config files when config directory doesn't exist."""
    with (
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=False),
    ):
        config = _load_environment_config_files()
        assert config == {}


def test_load_environment_config_files_default_yaml_error():
    """Test loading environment config files with error in default.yml."""

    class YamlErrorRaiser:
        def __call__(self, p):
            if "default.yml" in str(p):
                raise ConfigurationError("YAML error")
            return {}

    with (
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=True),
        patch("openmas.config._load_yaml_config", side_effect=YamlErrorRaiser()),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            _load_environment_config_files()
        assert "Error in default config file" in str(exc_info.value)


def test_load_environment_config_files_env_yaml_error():
    """Test loading environment config files with error in environment-specific YAML."""

    class YamlErrorRaiser:
        def __call__(self, p):
            if "default.yml" in str(p):
                return {}
            raise ConfigurationError("YAML error")

    with (
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=True),
        patch.dict(os.environ, {"OPENMAS_ENV": "prod"}),
        patch("openmas.config._load_yaml_config", side_effect=YamlErrorRaiser()),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            _load_environment_config_files()
        assert "Error in environment config file" in str(exc_info.value)
        assert "prod.yml" in str(exc_info.value)


def test_load_config_with_env_file_error():
    """Test load_config with error loading .env file."""
    # We should continue gracefully if .env file can't be loaded
    with (
        patch("openmas.config._find_project_root", return_value=Path("/project")),
        patch("pathlib.Path.exists", return_value=True),
        patch("dotenv.load_dotenv", side_effect=Exception("Failed to load .env")),
        patch("openmas.config._load_project_config", return_value={}),
        patch("openmas.config._load_environment_config_files", return_value={}),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent"}),
    ):
        # This should not raise an exception
        config = load_config(AgentConfig)
        assert config.name == "test-agent"


def test_load_config_shared_paths_from_project():
    """Test loading shared_paths from project config."""
    project_config = {"name": "test_project", "shared_paths": ["shared/utils", "shared/models"]}

    with (
        patch("openmas.config._load_project_config", return_value=project_config),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent"}),
    ):
        config = load_config(AgentConfig)
        assert config.shared_paths == ["shared/utils", "shared/models"]


def test_load_config_shared_paths_from_env():
    """Test loading shared_paths from environment variables."""
    shared_paths = ["env/utils", "env/models"]

    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent", "SHARED_PATHS": json.dumps(shared_paths)}),
    ):
        config = load_config(AgentConfig)
        assert config.shared_paths == shared_paths


def test_load_config_shared_paths_invalid_json():
    """Test handling invalid JSON in SHARED_PATHS."""
    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent", "SHARED_PATHS": "not-json"}),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "Invalid JSON in SHARED_PATHS" in str(exc_info.value)


def test_load_config_shared_paths_not_list():
    """Test handling non-list value in SHARED_PATHS."""
    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent", "SHARED_PATHS": '{"not": "list"}'}),
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(AgentConfig)
        assert "SHARED_PATHS must be a JSON array" in str(exc_info.value)


def test_load_config_extension_paths_from_project():
    """Test loading extension_paths from project config."""
    project_config = {"name": "test_project", "extension_paths": ["extensions/custom", "extensions/third-party"]}

    with (
        patch("openmas.config._load_project_config", return_value=project_config),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent"}),
    ):
        config = load_config(AgentConfig)
        assert config.extension_paths == ["extensions/custom", "extensions/third-party"]


def test_load_config_extension_paths_from_env():
    """Test loading extension_paths from environment variables."""
    extension_paths = ["env/custom", "env/third-party"]

    with (
        patch("openmas.config._load_project_config", return_value={}),
        patch.dict(os.environ, {"AGENT_NAME": "test-agent", "EXTENSION_PATHS": json.dumps(extension_paths)}),
    ):
        config = load_config(AgentConfig)
        assert config.extension_paths == extension_paths


class TestProjectConfig:
    """Tests for the ProjectConfig model."""

    def test_valid_config(self) -> None:
        """Test that a valid configuration passes validation."""
        config_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {
                "agent1": {
                    "module": "agents.agent1",
                    "class": "Agent1",
                }
            },
        }
        config = ProjectConfig(**config_data)
        assert config.name == "test-project"
        assert config.version == "0.1.0"
        assert "agent1" in config.agents
        assert config.agents["agent1"].module == "agents.agent1"
        assert config.agents["agent1"].class_ == "Agent1"

    def test_missing_required_fields(self) -> None:
        """Test that missing required fields raise a validation error."""
        # Missing name
        with pytest.raises(ValidationError):
            ProjectConfig(version="0.1.0", agents={})

        # Missing version
        with pytest.raises(ValidationError):
            ProjectConfig(name="test-project", agents={})

    def test_incorrect_types(self) -> None:
        """Test that incorrect types raise a validation error."""
        # Agents should be a dict, not a list
        with pytest.raises(ValidationError):
            ProjectConfig(name="test-project", version="0.1.0", agents=["agent1", "agent2"])

        # Non-string value should raise error
        with pytest.raises(ValidationError):
            ProjectConfig(
                name="test-project",
                version="0.1.0",
                agents={"agent1": {"module": "test", "class": 12345}},  # Integer for class instead of string
            )

    def test_agent_config_validation(self) -> None:
        """Test validation of agent configurations."""
        # Missing required field 'module'
        with pytest.raises(ValidationError):
            ProjectConfig(
                name="test-project",
                version="0.1.0",
                agents={
                    "agent1": {
                        "class": "Agent1",
                    }
                },
            )

    def test_default_values(self) -> None:
        """Test default values."""
        config = ProjectConfig(
            name="test-project",
            version="0.1.0",
            agents={
                "agent1": {
                    "module": "agents.agent1",
                    "class": "Agent1",
                }
            },
        )
        assert config.shared_paths == []
        assert config.extension_paths == []
        assert config.default_config == {}
        assert config.dependencies == []

    def test_agent_defaults(self) -> None:
        """Test agent default values."""
        config = ProjectConfig(
            name="test-project",
            version="0.1.0",
            agents={
                "agent1": {
                    "module": "agents.agent1",
                    "class": "Agent1",
                }
            },
            agent_defaults={"communicator": "http"},
        )
        # The agent_defaults is stored but not applied directly to agents
        assert config.agent_defaults == {"communicator": "http"}

        # Agent fields remain as specified
        assert config.agents["agent1"].module == "agents.agent1"
        assert config.agents["agent1"].class_ == "Agent1"
        assert config.agents["agent1"].communicator is None  # Default not applied yet

    def test_project_config_agent_name_validation(self):
        """Test that ProjectConfig validates agent names against the specified pattern."""
        # Valid agent names should be accepted
        valid_names = ["agent1", "test-agent", "my_agent", "Agent123"]
        for name in valid_names:
            config = ProjectConfig(
                name="test-project", version="0.1.0", agents={name: {"module": "agents.test", "class": "TestAgent"}}
            )
            assert name in config.agents

        # Invalid agent names should raise a validation error
        invalid_names = ["agent@123", "test.agent", "my agent", "agent/123", "agent$"]
        for name in invalid_names:
            with pytest.raises(ValidationError, match="Invalid agent name"):
                ProjectConfig(
                    name="test-project", version="0.1.0", agents={name: {"module": "agents.test", "class": "TestAgent"}}
                )

    def test_path_format_agents(self):
        """Test that ProjectConfig successfully parses agents defined using path format."""
        config_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {"agent1": "agents/agent1", "agent2": "agents/agent2.py", "agent3": "path/to/agent3"},
        }

        config = ProjectConfig(**config_data)

        # Check that all agents were processed correctly
        assert len(config.agents) == 3

        # Verify agents are converted to AgentConfigEntry objects
        assert config.agents["agent1"].module == "agents.agent1"
        assert config.agents["agent1"].class_ == "Agent"

        # Path with .py extension should have it removed
        assert config.agents["agent2"].module == "agents.agent2"
        assert config.agents["agent2"].class_ == "Agent"

        # Deeper paths should be handled correctly
        assert config.agents["agent3"].module == "path.to.agent3"
        assert config.agents["agent3"].class_ == "Agent"

    def test_dictionary_format_agents(self):
        """Test that ProjectConfig successfully parses agents defined using dictionary format."""
        config_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {
                "agent1": {"module": "agents.agent1", "class": "CustomAgent"},
                "agent2": {
                    "module": "agents.agent2",
                    "class": "Agent2",
                    "communicator": "http",
                    "options": {"timeout": 30},
                },
                "agent3": {"module": "path.to.agent3", "class": "Agent3", "deploy_config_path": "deploy/agent3.yml"},
            },
        }

        config = ProjectConfig(**config_data)

        # Check that all agents were processed correctly
        assert len(config.agents) == 3

        # Verify all fields were transferred correctly
        assert config.agents["agent1"].module == "agents.agent1"
        assert config.agents["agent1"].class_ == "CustomAgent"
        assert config.agents["agent1"].communicator is None
        assert config.agents["agent1"].options == {}

        assert config.agents["agent2"].module == "agents.agent2"
        assert config.agents["agent2"].class_ == "Agent2"
        assert config.agents["agent2"].communicator == "http"
        assert config.agents["agent2"].options == {"timeout": 30}

        assert config.agents["agent3"].module == "path.to.agent3"
        assert config.agents["agent3"].class_ == "Agent3"
        assert config.agents["agent3"].deploy_config_path == "deploy/agent3.yml"

    def test_mixed_format_agents(self):
        """Test that ProjectConfig handles a mix of path and dictionary format agents correctly."""
        config_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {
                "agent1": "agents/agent1",
                "agent2": {"module": "agents.agent2", "class": "CustomAgent2"},
            },
        }

        config = ProjectConfig(**config_data)

        # Check both formats were processed correctly
        assert config.agents["agent1"].module == "agents.agent1"
        assert config.agents["agent1"].class_ == "Agent"

        assert config.agents["agent2"].module == "agents.agent2"
        assert config.agents["agent2"].class_ == "CustomAgent2"

    def test_normalization_in_model_post_init(self):
        """Test the normalization logic in model_post_init method."""
        # Test with various path formats
        test_cases = [
            ("simple/path", "simple.path", "Agent"),
            ("path/with/extension.py", "path.with.extension", "Agent"),
            ("dot.notation.path", "dot.notation.path", "Agent"),  # Should remain unchanged
            ("mixed/path.with.dots", "mixed.path.with.dots", "Agent"),
        ]

        for input_path, expected_module, expected_class in test_cases:
            config = ProjectConfig(name="test-project", version="0.1.0", agents={"test_agent": input_path})

            assert config.agents["test_agent"].module == expected_module
            assert config.agents["test_agent"].class_ == expected_class

    def test_invalid_agent_config_type(self):
        """Test that ProjectConfig raises an error for invalid agent config type."""
        config_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {"agent1": 12345},  # Invalid type (integer)
        }

        with pytest.raises(ValidationError):
            ProjectConfig(**config_data)

        config_data = {
            "name": "test-project",
            "version": "0.1.0",
            "agents": {"agent2": [1, 2, 3]},  # Invalid type (list)
        }

        with pytest.raises(ValidationError):
            ProjectConfig(**config_data)


class TestConfigLoader:
    """Tests for the ConfigLoader class."""

    def test_load_yaml_file_invalid_yaml(self):
        """Test that loading a file with invalid YAML syntax raises a ConfigurationError."""
        from openmas.config import ConfigLoader

        # Create a temporary file with invalid YAML
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data="invalid: : yaml")),
            patch("yaml.safe_load", side_effect=yaml.YAMLError("YAML syntax error")),
        ):
            loader = ConfigLoader()

            with pytest.raises(ConfigurationError) as exc_info:
                loader.load_yaml_file(Path("/config/invalid.yml"))

            assert "Error parsing YAML file '/config/invalid.yml'" in str(exc_info.value)
            assert "YAML syntax error" in str(exc_info.value)
