#!/usr/bin/env python
"""
Simple MCP (Model Context Protocol) Example.

This script demonstrates the basic concepts of MCP with simple print statements.
"""

import asyncio
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_simple")


async def run_demo():
    """Run a simple MCP demo with print statements."""
    logger.info("=== MCP Simple Demo ===")

    # Server side
    logger.info("Server: Registering tools")
    logger.info("Server: Registering 'add' tool")
    logger.info("Server: Registering 'multiply' tool")
    logger.info("Server: Starting on port 8000")

    # Client side
    logger.info("Client: Connecting to server")
    logger.info("Client: Listing available tools")
    logger.info("Client: Found tool 'add' - Add two numbers")
    logger.info("Client: Found tool 'multiply' - Multiply two numbers")

    logger.info("Client: Calling 'add' tool with arguments 5 and 3")
    logger.info("Server: Processing 'add' tool call with arguments 5 and 3")
    logger.info("Server: Result of add(5, 3) = 8")
    logger.info("Client: Received result: 8")

    logger.info("=== MCP Demo Complete ===")


if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        logger.info("Demo terminated by user")
        sys.exit(0)
