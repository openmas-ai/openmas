# OpenMAS

[![PyPI version](https://img.shields.io/pypi/v/openmas.svg)](https://pypi.org/project/openmas/)
[![Python Version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI/CD](https://github.com/openmas-ai/openmas/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/openmas-ai/openmas/actions)
[![codecov](https://codecov.io/gh/openmas-ai/openmas/graph/badge.svg)](https://codecov.io/gh/openmas-ai/openmas)


**Build Intelligent Agent Systems**

OpenMAS is a lightweight Python SDK for building asynchronous Multi-Agent Systems (MAS) with first-class support for the Model Context Protocol (MCP).

It provides the essential tools and patterns to create sophisticated, independent agents that can communicate, coordinate, and interact with AI models and services.

**Full Documentation:** [**https://docs.openmas.ai**](https://docs.openmas.ai)

## Key Features

*   **Flexible Agent Framework:** Build agents using the `BaseAgent` class with clear lifecycle methods (`setup`, `run`, `shutdown`).
*   **Diverse Communication:** Support for HTTP, WebSockets, gRPC, MQTT, and first-class MCP integration.
*   **Environment Configuration:** Easily configure agents via environment variables or configuration files.
*   **Testing Utilities:** Includes tools like `MockCommunicator` and `AgentTestHarness`.
*   **Deployment Ready:** CLI tools to help generate Dockerfiles.
*   **Agent Patterns:** Built-in support for patterns like Orchestrator-Worker.
*   **Package Management:** Git-based dependency management for agents using `openmas deps`.

## Installation

```bash
pip install openmas
```

OpenMAS has optional extras for different communication protocols (`[mcp]`, `[grpc]`, `[mqtt]`, `[all]`).

See the full [Installation Guide](https://docs.openmas.ai/installation/) for details on prerequisites, virtual environments, and optional dependencies.

## Quick Start

Here's a basic agent:

```python
# hello_agent.py
import asyncio
from openmas.agent import BaseAgent

class HelloWorldAgent(BaseAgent):
    async def setup(self) -> None:
        """Initialize the agent."""
        self.logger.info(f"Setting up the {self.name}")

    async def run(self) -> None:
        """Run the agent."""
        self.logger.info("Hello from OpenMAS!")

        # Example: Sleep for a while then exit
        await asyncio.sleep(5)

        # Or for production agents that should run until stopped:
        # while True:
        #     await asyncio.sleep(3600)

    async def shutdown(self) -> None:
        """Clean up resources when the agent is stopped."""
        self.logger.info(f"Shutting down the {self.name}")

async def main():
    agent = HelloWorldAgent(name="hello-agent")  # Uses HttpCommunicator by default
    try:
        await agent.start()
    except KeyboardInterrupt:
        pass
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Run it with `python hello_agent.py`.

For a more detailed walkthrough, see the [Getting Started Guide](https://docs.openmas.ai/getting_started/).

## Contributing

Contributions are welcome! Please see the [Contributing Guide](https://docs.openmas.ai/contributing/) for details on how to get involved, set up your development environment, run tests (`tox`), and submit pull requests.

## License

OpenMAS is licensed under the [MIT License](LICENSE).
