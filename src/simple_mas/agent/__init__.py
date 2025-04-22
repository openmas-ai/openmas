"""SimpleMAS agent module."""

from simple_mas.agent.base import BaseAgent
from simple_mas.agent.mcp import McpAgent, mcp_prompt, mcp_resource, mcp_tool

__all__ = ["BaseAgent", "McpAgent", "mcp_tool", "mcp_prompt", "mcp_resource"]
