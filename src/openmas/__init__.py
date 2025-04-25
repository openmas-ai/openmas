"""OpenMAS: A lightweight SDK for building Multi-Agent Systems."""

__version__ = "0.1.0"

# Direct exports from agent module
from openmas.agent.base import BaseAgent
from openmas.agent.bdi import BdiAgent
from openmas.agent.mcp import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.agent.mcp_server import McpServerAgent
from openmas.agent.spade_bdi_agent import SpadeBdiAgent

__all__ = [
    "BaseAgent",
    "BdiAgent",
    "McpAgent",
    "McpServerAgent",
    "SpadeBdiAgent",
    "mcp_tool",
    "mcp_prompt",
    "mcp_resource",
]
