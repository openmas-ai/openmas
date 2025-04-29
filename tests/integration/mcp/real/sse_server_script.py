#!/usr/bin/env python
"""Simple MCP SSE server for integration testing (Uvicorn + FastAPI Approach)."""

import argparse
import asyncio
import json
import logging
import sys

import uvicorn
from fastapi import FastAPI, Request  # Import FastAPI
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.sse import SseServerTransport  # Import SSE Transport
from starlette.routing import Mount

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("sse_server")

# 1. Create FastAPI app instance
app = FastAPI(title="MCP Test Server", version="1.0")

# 2. Create the MCP server instance
mcp_server = FastMCP(
    name="TestSseServer",
    log_level="DEBUG",
)

# 3. Create SSE Transport
# Use a distinct path for message posting if needed, though FastMCP might handle this internally via /sse
# Sticking to the example pattern for now.
sse_transport = SseServerTransport("/messages/")  # Path for posting messages back (client->server)

# --- Add Mount for POST messages ---
app.router.routes.append(Mount("/messages", app=sse_transport.handle_post_message))
# ---------------------------------


# Define the echo tool on the MCP server instance
@mcp_server.tool(name="echo", description="Echo back the input message")
async def echo(ctx: Context, message: any) -> str:
    logger.debug(f"Echo tool called with message: {message!r} (type: {type(message)})")
    try:
        # Return the message wrapped in a standard JSON structure
        response_obj = {"echoed": message}
        json_response = json.dumps(response_obj)
        logger.debug(f"Returning echo response JSON: {json_response}")
        # Return just the JSON string - let MCP library handle wrapping?
        return json_response
    except Exception as e:
        logger.error(f"Error in echo tool: {e}", exc_info=True)
        # If returning a simple string on success, maybe return error string too?
        # However, the framework should ideally handle raising/returning errors.
        # Let's try raising the exception to see if FastMCP catches and formats it.
        raise  # Re-raise the original exception


# 4. Define the /sse endpoint on the FastAPI app
@app.get("/sse", tags=["MCP"])
async def handle_sse(request: Request):
    """Handle SSE connection requests and run the MCP server."""
    logger.info(f"Incoming SSE connection request from {request.client}")
    try:
        # Use sse_transport.connect_sse to establish the connection
        # This context manager handles the SSE handshake and provides streams
        async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (
            read_stream,
            write_stream,
        ):
            logger.info("SSE connection established, running MCP server loop.")
            # Run the actual MCP server logic using the established streams
            await mcp_server._mcp_server.run(
                read_stream,
                write_stream,
                mcp_server._mcp_server.create_initialization_options(),
            )
            logger.info("MCP server loop finished for this connection.")
    except Exception as e:
        # Log errors during SSE connection handling
        logger.error(f"Error during SSE handling: {e}", exc_info=True)
        # Depending on where the error occurs, a response might have already been sent.
        # Raising here might not be effective, but logging is important.
        raise  # Re-raise for potential higher-level handling if possible


# Optional: Add a root endpoint for basic health/info check
@app.get("/", tags=["General"])
async def read_root():
    return {"message": "MCP SSE Test Server is running. Connect via /sse."}


async def main():
    parser = argparse.ArgumentParser(description="MCP SSE test server (FastAPI)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    try:
        config = uvicorn.Config(app=app, host=args.host, port=args.port, log_level="debug")  # Run the FastAPI app
        server = uvicorn.Server(config)

        # Print URL before starting - crucial for harness
        sys.stderr.write(f"SSE_SERVER_URL=http://{args.host}:{args.port}\n")
        sys.stderr.flush()

        logger.info(f"Starting Uvicorn server for FastAPI+MCP on {args.host}:{args.port}")
        await server.serve()

    except Exception as e:
        logger.error(f"Error starting or running server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logger.info("Starting main function")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Unhandled exception in top-level: {e}", exc_info=True)
        sys.exit(1)
