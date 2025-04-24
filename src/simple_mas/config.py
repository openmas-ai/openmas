"""Configuration management for SimpleMAS."""

import json
import os
from typing import Any, Dict, Type, TypeVar

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


def load_config(config_model: Type[T], prefix: str = "") -> T:
    """Load configuration from environment variables.

    Args:
        config_model: The Pydantic model to use for validation
        prefix: Optional prefix for environment variables

    Returns:
        A validated configuration object

    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    try:
        # Build a dictionary from environment variables
        config_data: Dict[str, Any] = {}
        env_prefix = f"{prefix}_" if prefix else ""

        # First check for a JSON config string
        json_config = os.environ.get(f"{env_prefix}CONFIG")
        if json_config:
            try:
                config_data = json.loads(json_config)
                logger.debug("Loaded configuration from JSON", source=f"{env_prefix}CONFIG")
            except json.JSONDecodeError as e:
                raise ConfigurationError(f"Invalid JSON in {env_prefix}CONFIG: {e}")

        # Get the agent name
        if "name" not in config_data:
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
