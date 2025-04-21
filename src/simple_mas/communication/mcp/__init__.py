"""MCP communicator implementations for SimpleMAS."""

try:
    from simple_mas.communication.mcp.mcp_adapter import McpClientAdapter, McpServerWrapper

    __all__ = ["McpClientAdapter", "McpServerWrapper"]
except ImportError:
    # Define dummy classes that raise ImportError when used
    class McpClientAdapter:
        def __init__(self, *args, **kwargs):
            raise ImportError("MCP package is not installed")

    class McpServerWrapper:
        def __init__(self, *args, **kwargs):
            raise ImportError("MCP package is not installed")

    __all__ = ["McpClientAdapter", "McpServerWrapper"]
