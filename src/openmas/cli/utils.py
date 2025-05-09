"""Utility functions for the OpenMAS CLI."""

import os
from pathlib import Path
from typing import Optional

import yaml

from openmas.config import ProjectConfig
from openmas.logging import get_logger

logger = get_logger(__name__)


def load_project_config(project_dir: Optional[Path] = None) -> ProjectConfig:
    """Load the project configuration from the openmas_project.yml file.

    Args:
        project_dir: Optional explicit path to the project directory.
            If not provided, it will try to find the project directory
            by checking the current directory and parent directories.

    Returns:
        The ProjectConfig object with the parsed configuration.

    Raises:
        FileNotFoundError: If the openmas_project.yml file cannot be found.
        ValueError: If the configuration file is invalid or cannot be parsed.
    """
    # Check if OPENMAS_PROJECT_PATH environment variable is set
    env_project_path = os.environ.get("OPENMAS_PROJECT_PATH")
    if env_project_path:
        env_path = Path(env_project_path)
        if env_path.is_file() or env_project_path.endswith((".yml", ".yaml")):
            # If it's a file or has a YAML extension, use it directly
            project_file = env_path
        else:
            # Otherwise, treat it as a directory
            project_file = env_path / "openmas_project.yml"
    elif project_dir:
        project_file = project_dir / "openmas_project.yml"
    else:
        # Try to find the project file in the current directory or parents
        current_dir = Path.cwd()
        project_file = None

        # Check the current directory and up to 5 parent directories
        for _ in range(6):
            candidate = current_dir / "openmas_project.yml"
            if candidate.exists():
                project_file = candidate
                break
            parent = current_dir.parent
            if parent == current_dir:  # Reached the root directory
                break
            current_dir = parent

    if not project_file or not project_file.exists():
        logger.error("Could not find openmas_project.yml file")
        raise FileNotFoundError("Could not find openmas_project.yml file")

    try:
        with open(project_file, "r") as f:
            project_data = yaml.safe_load(f)

        # Parse the project configuration
        project_config = ProjectConfig.model_validate(project_data)
        return project_config

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse openmas_project.yml: {str(e)}")
        raise ValueError(f"Failed to parse openmas_project.yml: {str(e)}")
    except Exception as e:
        logger.error(f"Invalid configuration in openmas_project.yml: {str(e)}")
        raise ValueError(f"Invalid configuration in openmas_project.yml: {str(e)}")
