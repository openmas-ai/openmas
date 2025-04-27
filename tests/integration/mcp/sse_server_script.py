#!/usr/bin/env python
"""Simple MCP SSE server for integration testing."""

import argparse
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("sse_server")


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle FastAPI application lifespan events.

    Args:
        app: The FastAPI application
    """
    logger.info("Server starting up")
    yield
    logger.info("Server shutting down")


async def start_test_only_server():
    """Start a minimal server that just handles the test-only case."""
    app = FastAPI(lifespan=lifespan)

    @app.get("/test-only")
    async def test_only():
        """Return a test response to verify the server is working."""
        logger.info("Test-only endpoint called")
        return {
            "jsonrpc": "2.0",
            "id": "test-only-mode",
            "method": "test",
            "params": {"message": "Test-only mode working properly"},
        }

    return app


async def start_mcp_server():
    """Initialize and run the MCP server over SSE."""
    app = FastAPI(title="MCP SSE Test Server", lifespan=lifespan)

    # Create a FastMCP server instance
    logger.info("Creating FastMCP server instance")
    mcp_server = FastMCP(
        name="TestSseServer",
        instructions="Test SSE server for integration testing",
        log_level="DEBUG",
    )
    logger.debug("Created FastMCP server instance")

    # Add the echo tool
    logger.info("Registering echo tool")
    mcp_server.add_tool(fn=echo, name="echo", description="Echo back the input message")
    logger.debug("Registered echo tool")

    # Mount the FastMCP server to the FastAPI app
    if hasattr(mcp_server, "router"):
        app.mount("/mcp", mcp_server.router)
        logger.info("Mounted MCP server using server.router")
    else:
        logger.error("Failed to mount MCP server: No router attribute found")
        raise RuntimeError("Failed to mount MCP server: No router attribute found")

    # Add a simple test endpoint to verify the server is working
    @app.get("/test")
    async def test():
        """Return a test response to verify the server is working."""
        logger.info("Test endpoint called")
        return {
            "status": "ok",
            "message": "MCP SSE server is running",
        }

    return app


async def main():
    """Parse arguments and start the appropriate server."""
    parser = argparse.ArgumentParser(description="MCP SSE test server")
    parser.add_argument("--test-only", action="store_true", help="Run in test-only mode")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    if args.test_only:
        logger.info("Test-only mode detected")
        app = await start_test_only_server()
        logger.info("Test-only server ready")
    else:
        logger.info("Starting MCP SSE server")
        app = await start_mcp_server()
        logger.info("MCP server ready")

    config = uvicorn.Config(
        app=app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info(f"Starting server on {args.host}:{args.port}")

    # Write the server address to stderr so the test can connect to it
    sys.stderr.write(f"SSE_SERVER_URL=http://{args.host}:{args.port}\n")
    sys.stderr.flush()

    await server.serve()


if __name__ == "__main__":
    logger.info("Starting main function")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
