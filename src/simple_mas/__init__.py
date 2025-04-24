"""SimpleMAS: A lightweight SDK for building Multi-Agent Systems."""

__version__ = "0.1.0"

# Direct exports from agent module
from simple_mas.agent.base import BaseAgent
from simple_mas.agent.bdi import BdiAgent
from simple_mas.agent.mcp import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from simple_mas.agent.mcp_server import McpServerAgent
from simple_mas.agent.spade_bdi_agent import SpadeBdiAgent

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
