#!/usr/bin/env python
"""Simple MCP stdio server for integration testing."""

import asyncio
import json
import logging
import sys
import time
from typing import Dict, Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult

# Set up logging - IMPORTANT: log only to stderr
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        # Log ONLY to stderr for visibility in test output
        # This is critical - stdout is reserved for JSON-RPC messages
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("stdio_server")

async def echo(ctx: Context, message: str) -> CallToolResult:
    """Echo back the input message.
    
    Args:
        ctx: The MCP context
        message: The message to echo
        
    Returns:
        A CallToolResult containing the echoed message
    """
    logger.debug(f"Echo tool called with message: {message}")
    return CallToolResult({"echoed": message})


async def main() -> None:
    """Initialize and run the MCP server over stdio."""
    logger.info("Starting MCP stdio server")
    
    # Check if we're in test-only mode early
    if "--test-only" in sys.argv:
        logger.info("Test-only mode detected")
        # Send a simple test message and exit
        test_message = {
            "jsonrpc": "2.0",
            "id": "test-only-mode",
            "method": "test",
            "params": {"message": "Test-only mode working properly"}
        }
        
        try:
            # Print directly to stdout and flush
            message_bytes = (json.dumps(test_message) + "\n").encode("utf-8")
            sys.stdout.buffer.write(message_bytes)
            sys.stdout.buffer.flush()
            logger.info("Test-only mode successful")
            # Exit with success
            return
        except Exception as e:
            logger.error(f"Test-only mode failed: {e}")
            raise
    
    # Send a test message directly to stdout to verify it's working
    # This bypasses the MCP protocol but helps diagnose communication issues
    test_message = {
        "jsonrpc": "2.0",
        "id": "test-init",
        "method": "test",
        "params": {"message": "Initial test message from server"}
    }
    
    logger.info("Sending test message to stdout")
    try:
        # Print directly to stdout and flush to ensure it's sent immediately
        message_bytes = (json.dumps(test_message) + "\n").encode("utf-8")
        sys.stdout.buffer.write(message_bytes)
        sys.stdout.buffer.flush()
        logger.debug("Test message sent successfully")
    except Exception as e:
        logger.error(f"Failed to send test message: {e}")
        raise
    
    try:
        # Create a FastMCP server instance with debug logging
        logger.info("Creating FastMCP server instance")
        mcp_server = FastMCP("TestStdioServer", log_level="DEBUG")
        logger.debug("Created FastMCP server instance")
        
        # Add the echo tool - using the correct API signature
        logger.info("Registering echo tool")
        mcp_server.add_tool(
            fn=echo,
            name="echo",
            description="Echo back the input message"
        )
        logger.debug("Registered echo tool")
        
        # Explicitly flush stdout to ensure previous messages are sent
        sys.stdout.buffer.flush()
        
        # Run the server - make sure to call the correct function
        logger.info("Starting to serve over stdio")
        
        # run_stdio_async() doesn't take any parameters
        # It internally uses sys.stdin.buffer and sys.stdout.buffer
        logger.debug("Starting MCP server with run_stdio_async()")
        try:
            # Call with no arguments - it internally uses stdin/stdout
            await mcp_server.run_stdio_async()
        except Exception as e:
            logger.error(f"Error running MCP server: {e}", exc_info=True)
            raise
        
        logger.info("Server finished running")
    except Exception as e:
        logger.error(f"Error in MCP stdio server: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    logger.info("Starting main function")
    try:
        # Explicitly flush stdout at startup
        sys.stdout.flush()
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1) 