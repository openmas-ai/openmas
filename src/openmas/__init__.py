"""OpenMAS: A lightweight SDK for building Multi-Agent Systems."""

__version__ = "0.1.0"

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
