#!/usr/bin/env python
"""Example of using the gRPC communicator with OpenMAS.

This example shows how to create an agent with a gRPC communicator
and demonstrates request/response and notification patterns.

To run this example:
1. First, install the required dependencies:
   pip install grpcio grpcio-tools protobuf

2. Generate the protobuf code:
   cd src/openmas/communication/grpc && python generate_proto.py

3. Run the server agent:
   python examples/grpc_example.py --server

4. In another terminal, run the client agent:
   python examples/grpc_example.py --client
"""

import argparse
import asyncio
import logging
import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openmas.agent import BaseAgent  # noqa: E402
from openmas.config import AgentConfig  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class EchoAgent(BaseAgent):
    """Example agent with gRPC communication."""

    async def setup(self) -> None:
        """Set up the agent by registering handlers."""
        await self.communicator.register_handler("echo", self.handle_echo)
        logger.info(f"Agent {self.name} ready")

    async def run(self) -> None:
        """Run the agent's main loop."""
        while True:
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        """Clean up resources when shutting down."""
        logger.info(f"Agent {self.name} shutting down")

    async def handle_echo(self, message: str) -> dict:
        """Echo handler that returns the received message."""
        logger.info(f"Received: {message}")
        return {"echo": message}


async def run_server():
    """Run a gRPC server agent."""
    agent = EchoAgent(
        config=AgentConfig(
            name="grpc_server",
            communicator_type="grpc",
            communicator_options={"server_mode": True},
            service_urls={},
        )
    )

    await agent.start()

    try:
        print("Server running on localhost:50051. Press Ctrl+C to exit.")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await agent.stop()


async def run_client():
    """Run a gRPC client agent."""
    agent = EchoAgent(
        config=AgentConfig(
            name="grpc_client",
            communicator_type="grpc",
            service_urls={"server": "localhost:50051"},
        )
    )

    await agent.start()

    try:
        print("Sending echo request...")
        response = await agent.communicator.send_request("server", "echo", {"message": "Hello, gRPC world!"})
        print(f"Response: {response}")
    finally:
        await agent.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="gRPC example for OpenMAS")
    parser.add_argument("mode", choices=["server", "client"], help="Run as server or client")
    args = parser.parse_args()

    if args.mode == "server":
        asyncio.run(run_server())
    else:
        asyncio.run(run_client())
