#!/usr/bin/env python
"""A simple stdio server for testing the MCP stdio transport."""

import asyncio
import json
import logging
import sys
from typing import Any, Dict

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, TextContent

# Set up logging - IMPORTANT: log only to stderr
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        # Log ONLY to stderr for visibility in test output
        # This is critical - stdout is reserved for JSON-RPC messages
        logging.StreamHandler(sys.stderr)
    ],
)
logger = logging.getLogger(__name__)

# Server instance - Create with explicit debugging
logger.debug("Creating FastMCP server instance")
server = FastMCP("TestStdioServer", log_level="DEBUG")
logger.debug("FastMCP server instance created")


# A simple echo tool that returns the input message
@server.tool("echo", description="Echo back the input message")
async def echo(context: Context, message: Any = None) -> CallToolResult:
    """A simple echo tool that returns exactly what it received.

    Args:
        context: The MCP context
        message: The message to echo back, may be a direct value or nested in a dictionary
    """
    try:
        logger.debug(f"Echo received: {message} of type {type(message)}")

        # Handle message that might be wrapped in a dictionary
        actual_message = message
        if isinstance(message, dict) and "message" in message:
            actual_message = message["message"]
            logger.debug(f"Extracted message from dict: {actual_message}")

        # Simply return the exact message we received - don't wrap in JSON
        logger.debug(f"Echo returning: {actual_message}")
        if isinstance(actual_message, (dict, list)):
            # For compound objects, convert to JSON string
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(actual_message))])
        else:
            # For primitive types, convert to string directly
            return CallToolResult(
                content=[TextContent(type="text", text=str(actual_message) if actual_message is not None else "null")]
            )
    except Exception as e:
        logger.error(f"Error in echo tool: {e}")
        return CallToolResult(content=[TextContent(type="text", text=json.dumps({"error": str(e)}))])


# Define the main coroutine
async def main() -> None:
    """Run the MCP stdio server with proper async handling."""
    logger.debug("Starting MCP stdio server")

    # Explicitly flush stdout before running the server
    sys.stdout.flush()

    # Run the server with proper async handling
    await server.run_stdio_async()


# Use run_stdio_async method which handles the event loop and stream setup
if __name__ == "__main__":
    # Check for --test-only flag
    if "--test-only" in sys.argv:
        logger.info("Test-only mode detected")
        # Write expected test message to stdout
        test_message = {
            "jsonrpc": "2.0",
            "id": "test-only-mode",
            "method": "test",
            "params": {"message": "Test-only mode successful"},
        }
        sys.stdout.write(json.dumps(test_message) + "\n")
        sys.stdout.flush()
        logger.info("Test-only mode successful")
        sys.exit(0)  # Exit successfully after printing test message

    # If not --test-only, run the full server
    logger.info("Starting main function")
    try:
        # Explicitly flush stdout at startup
        sys.stdout.flush()

        # Log server ready state
        logger.debug("Server ready to start")

        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
