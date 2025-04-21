"""Communication module for SimpleMAS."""

from simple_mas.communication.base import BaseCommunicator
from simple_mas.communication.http import HttpCommunicator

# Try to import MCP components, but don't fail if the MCP package isn't installed
try:
    from simple_mas.communication.mcp import McpClientAdapter, McpServerWrapper

    __all__ = ["BaseCommunicator", "HttpCommunicator", "McpClientAdapter", "McpServerWrapper"]
except ImportError:
    __all__ = ["BaseCommunicator", "HttpCommunicator"]
