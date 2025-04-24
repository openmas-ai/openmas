"""Configuration management for SimpleMAS."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, cast

import yaml
from dotenv import load_dotenv  # type: ignore
from pydantic import BaseModel, Field, ValidationError

from simple_mas.exceptions import ConfigurationError
from simple_mas.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class AgentConfig(BaseModel):
    """Base configuration model for agents."""

    name: str = Field(..., description="The name of the agent")
    log_level: str = Field("INFO", description="Logging level")
    service_urls: Dict[str, str] = Field(default_factory=dict, description="Mapping of service names to URLs")
    communicator_type: str = Field("http", description="Type of communicator to use (e.g., 'http', 'mcp_stdio')")
    communicator_options: Dict[str, Any] = Field(
        default_factory=dict, description="Additional options specific to the selected communicator"
    )
    extension_paths: list[str] = Field(
        default_factory=list, description="List of paths to search for project-local extensions"
    )


def _find_project_root(project_dir: Optional[Path] = None) -> Optional[Path]:
    """Find the SimpleMas project root by looking for simplemas_project.yml.

    Args:
        project_dir: Optional explicit path to the project directory. If provided,
                    will check if this directory contains a simplemas_project.yml file.

    Returns:
        Path to the project root directory or None if not found
    """
    # If a project directory is explicitly provided, check if it contains the project file
    if project_dir is not None:
        project_dir = Path(project_dir).resolve()
        if (project_dir / "simplemas_project.yml").exists():
            return project_dir
        else:
            logger.warning(f"No simplemas_project.yml found in specified project directory: {project_dir}")
            return None

    # Otherwise, search for the project file in current and parent directories
    current_dir = Path.cwd()

    # Try current directory first
    if (current_dir / "simplemas_project.yml").exists():
        return current_dir

    # Then check parent directories (limit to a reasonable depth to avoid infinite loops)
    for _ in range(10):  # Maximum depth of 10 directories
        current_dir = current_dir.parent
        if (current_dir / "simplemas_project.yml").exists():
            return current_dir

    return None


def _load_yaml_config(file_path: Path) -> Dict[str, Any]:
    """Load and parse a YAML configuration file.

    Args:
        file_path: Path to the YAML configuration file

    Returns:
        Dictionary containing the parsed YAML or empty dict if file doesn't exist

    Raises:
        ConfigurationError: If the file exists but parsing fails
    """
    if not file_path.exists():
        logger.debug(f"Config file not found: {file_path}")
        return {}

    try:
        with open(file_path, "r") as f:
            result = yaml.safe_load(f)
            if result is None or not isinstance(result, dict):
                logger.warning(f"Config file {file_path} does not contain a dictionary")
                return {}
            return cast(Dict[str, Any], result)
    except Exception as e:
        message = f"Failed to load config file {file_path}: {e}"
        logger.error(message)
        raise ConfigurationError(message)


def _deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries.

    The override dictionary values take precedence over base values.
    If both values are dictionaries, they are merged recursively.

    Args:
        base: Base dictionary
        override: Dictionary with override values

    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _load_project_config(project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load the SimpleMas project config from YAML.

    Args:
        project_dir: Optional explicit path to the project directory.

    Returns:
        Dictionary containing the project configuration
    """
    config: Dict[str, Any] = {}

    # First check if the project config is provided in environment variable
    # (set by the CLI when running agents)
    project_config_env = os.environ.get("SIMPLEMAS_PROJECT_CONFIG")
    if project_config_env:
        try:
            result = yaml.safe_load(project_config_env)
            if result is None or not isinstance(result, dict):
                logger.warning("Project config from environment is not a dictionary")
                return {}
            return cast(Dict[str, Any], result)
        except Exception as e:
            logger.warning(f"Failed to parse project config from environment: {e}")
            return {}

    # Otherwise, try to load from file
    project_root = _find_project_root(project_dir)
    if project_root:
        try:
            config_path = project_root / "simplemas_project.yml"
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
            logger.info(f"Loaded project config from {config_path}")
        except Exception as e:
            logger.error(f"Error loading project config: {e}")
    else:
        logger.warning("No simplemas_project.yml found in project directory")

    return config


def _load_env_file(project_dir: Optional[Path] = None) -> None:
    """Load environment variables from .env file at the project root.

    Args:
        project_dir: Optional explicit path to the project directory.

    Uses python-dotenv with override=True to ensure env vars take precedence if also set directly.
    """
    project_root = _find_project_root(project_dir)
    if not project_root:
        logger.debug("Project root not found, skipping .env file loading")
        return

    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.debug(f"Loaded environment variables from {env_file}")


def _load_environment_config_files(project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from environment-specific YAML files.

    Args:
        project_dir: Optional explicit path to the project directory.

    Loads config/default.yml and config/<SIMPLEMAS_ENV>.yml if they exist.
    The environment-specific config overrides default config.

    Returns:
        A dictionary containing merged configuration from files
    """
    config_data: Dict[str, Any] = {}
    project_root = _find_project_root(project_dir)

    if not project_root:
        logger.debug("Project root not found, skipping config file loading")
        return {}

    # Load default config file
    default_config_path = project_root / "config" / "default.yml"
    default_config = _load_yaml_config(default_config_path)
    if default_config:
        logger.debug(f"Loaded default configuration from {default_config_path}")
        config_data = default_config

    # Load environment-specific config if SIMPLEMAS_ENV is set
    # If SIMPLEMAS_ENV is not set, default to 'local'
    env_name = os.environ.get("SIMPLEMAS_ENV", "local")
    env_config_path = project_root / "config" / f"{env_name}.yml"
    env_config = _load_yaml_config(env_config_path)
    if env_config:
        logger.debug(f"Loaded environment configuration from {env_config_path}")
        config_data = _deep_merge_dicts(config_data, env_config)

    return config_data


def load_config(config_model: Type[T], prefix: str = "", project_dir: Optional[Path] = None) -> T:
    """Load configuration from files, environment variables and project configuration.

    Configuration is loaded in the following order (lowest to highest precedence):
    1. SimpleMas SDK Internal Defaults (in the Pydantic model)
    2. default_config section in simplemas_project.yml
    3. config/default.yml file
    4. config/<SIMPLEMAS_ENV>.yml file (default: local.yml if SIMPLEMAS_ENV not set)
    5. .env file at project root
    6. Environment Variables (highest precedence)

    Args:
        config_model: The Pydantic model to use for validation
        prefix: Optional prefix for environment variables
        project_dir: Optional explicit path to the project directory

    Returns:
        A validated configuration object

    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    try:
        # Load environment variables from .env file (if exists)
        _load_env_file(project_dir)

        # Build a dictionary from environment variables and project configuration
        config_data: Dict[str, Any] = {}
        env_prefix = f"{prefix}_" if prefix else ""

        # Load project configuration and extract default_config
        project_config = _load_project_config(project_dir)
        default_config = project_config.get("default_config", {})

        # Apply default config as base layer
        if default_config:
            logger.debug("Applying default configuration from project config")
            config_data.update(default_config)

        # Load and apply configuration from YAML files
        yaml_config = _load_environment_config_files(project_dir)
        if yaml_config:
            logger.debug("Applying configuration from YAML files")
            config_data = _deep_merge_dicts(config_data, yaml_config)

        # First check for a JSON config string
        json_config = os.environ.get(f"{env_prefix}CONFIG")
        if json_config:
            try:
                env_config_data = json.loads(json_config)
                config_data.update(env_config_data)
                logger.debug("Loaded configuration from JSON", source=f"{env_prefix}CONFIG")
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in {env_prefix}CONFIG: {e}")

        # Get the agent name - this must be explicitly provided or validation will fail
        name = os.environ.get(f"{env_prefix}AGENT_NAME")
        if name:
            config_data["name"] = name

        # Load service URLs from environment
        service_urls_str = os.environ.get(f"{env_prefix}SERVICE_URLS")
        if service_urls_str:
            try:
                service_urls = json.loads(service_urls_str)
                if not isinstance(service_urls, dict):
                    raise ConfigurationError(f"{env_prefix}SERVICE_URLS must be a JSON dictionary")
                config_data["service_urls"] = service_urls
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in {env_prefix}SERVICE_URLS: {e}")

        # Load individual service URLs if defined
        for key, value in os.environ.items():
            if key.startswith(f"{env_prefix}SERVICE_URL_"):
                service_name = key[len(f"{env_prefix}SERVICE_URL_") :].lower()
                if "service_urls" not in config_data:
                    config_data["service_urls"] = {}
                config_data["service_urls"][service_name] = value

        # Load log level
        log_level = os.environ.get(f"{env_prefix}LOG_LEVEL")
        if log_level:
            config_data["log_level"] = log_level

        # Load communicator configuration
        communicator_type = os.environ.get(f"{env_prefix}COMMUNICATOR_TYPE")
        if communicator_type:
            config_data["communicator_type"] = communicator_type

        # Load communicator options
        communicator_options_str = os.environ.get(f"{env_prefix}COMMUNICATOR_OPTIONS")
        if communicator_options_str:
            try:
                communicator_options = json.loads(communicator_options_str)
                if not isinstance(communicator_options, dict):
                    raise ConfigurationError(f"{env_prefix}COMMUNICATOR_OPTIONS must be a JSON dictionary")

                # Use deep merge to combine options while preserving nested dictionaries
                if "communicator_options" in config_data:
                    config_data["communicator_options"] = _deep_merge_dicts(
                        config_data["communicator_options"], communicator_options
                    )
                else:
                    config_data["communicator_options"] = communicator_options
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in {env_prefix}COMMUNICATOR_OPTIONS: {e}")

        # Load extension paths
        extension_paths_str = os.environ.get(f"{env_prefix}EXTENSION_PATHS")
        if extension_paths_str:
            try:
                extension_paths = json.loads(extension_paths_str)
                if not isinstance(extension_paths, list):
                    raise ConfigurationError(f"{env_prefix}EXTENSION_PATHS must be a JSON array")
                config_data["extension_paths"] = extension_paths
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in {env_prefix}EXTENSION_PATHS: {e}")

        # Add extension paths from project config if available
        if "extension_paths" in project_config:
            project_extension_paths = project_config["extension_paths"]
            if "extension_paths" not in config_data:
                config_data["extension_paths"] = []
            config_data["extension_paths"].extend(project_extension_paths)

        # Load individual communicator options
        for key, value in os.environ.items():
            if key.startswith(f"{env_prefix}COMMUNICATOR_OPTION_"):
                option_name = key[len(f"{env_prefix}COMMUNICATOR_OPTION_") :].lower()
                if "communicator_options" not in config_data:
                    config_data["communicator_options"] = {}

                # Try to parse the value as JSON, fallback to string if it fails
                try:
                    option_value = json.loads(value)
                    config_data["communicator_options"][option_name] = option_value
                except json.JSONDecodeError:
                    config_data["communicator_options"][option_name] = value

        # Validate and create the configuration object
        config = config_model(**config_data)
        logger.debug("Configuration loaded successfully", config=config.model_dump())
        return config

    except ValidationError as e:
        error_msg = f"Configuration validation failed: {e}"
        logger.error(error_msg)
        raise ConfigurationError(error_msg)
    except Exception as e:
        error_msg = f"Failed to load configuration: {e}"
        logger.error(error_msg)
        raise ConfigurationError(error_msg)
