"""OpenMAS: A lightweight framework for building Multi-Agent Systems."""

import importlib.metadata
import os
import pathlib

# =========================================================================
# Version handling - single source of truth is pyproject.toml
# =========================================================================
# This implementation has three fallback mechanisms:
# 1. First try to get version via importlib.metadata (when properly installed)
# 2. If that fails, try to read directly from pyproject.toml (dev environment)
# 3. If all else fails, use a hardcoded version with -dev suffix for clarity
#
# This ensures the version is always accurate, and the -dev suffix makes it
# clear when running from a development environment rather than an installed package
# =========================================================================
try:
    __version__ = importlib.metadata.version("openmas")
except importlib.metadata.PackageNotFoundError:
    # Development mode - read directly from pyproject.toml
    try:
        import tomli  # type: ignore

        # Try to find the pyproject.toml file
        current_dir = pathlib.Path(__file__).parent
        for parent in [current_dir] + list(current_dir.parents):
            pyproject_path = parent / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    pyproject_data = tomli.load(f)
                    __version__ = pyproject_data["tool"]["poetry"]["version"]
                break
        else:
            # If we couldn't find it, use a dev version
            __version__ = "0.0.0-dev"
    except (ImportError, KeyError, FileNotFoundError):
        # If all else fails, use a dev version
        __version__ = "0.0.0-dev"

# Direct exports from agent module
from openmas.agent.base import BaseAgent
from openmas.agent.bdi import BdiAgent
from openmas.agent.mcp import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.agent.mcp_prompt import PromptMcpAgent
from openmas.agent.mcp_server import McpServerAgent
from openmas.agent.spade_bdi_agent import SpadeBdiAgent

# Exports from prompt module
from openmas.prompt import Prompt, PromptManager

# Exports from sampling module
from openmas.sampling import BaseSampler, SamplingResult

__all__ = [
    # Agents
    "BaseAgent",
    "BdiAgent",
    "McpAgent",
    "PromptMcpAgent",
    "McpServerAgent",
    "SpadeBdiAgent",
    # MCP decorators
    "mcp_tool",
    "mcp_prompt",
    "mcp_resource",
    # Prompt management
    "Prompt",
    "PromptManager",
    # Sampling
    "BaseSampler",
    "SamplingResult",
]
