# OpenMAS

[![PyPI version](https://img.shields.io/pypi/v/chesspal-mcp-engine.svg)](https://pypi.org/project/chesspal-mcp-engine/)
[![Python Version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
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

See the full [Installation Guide](https://docs.openmas.ai/guides/installation/) for details on prerequisites, virtual environments, and optional dependencies.

## Quick Start

Here's a basic agent:

```python
# hello_agent.py
import asyncio
from openmas.agent import BaseAgent
from openmas.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

class HelloAgent(BaseAgent):
    async def setup(self) -> None:
        logger.info(f"Agent '{self.name}' setting up.")
        await self.communicator.register_handler("greet", self.handle_greet)

    async def run(self) -> None:
        logger.info(f"Agent '{self.name}' running...")
        while True: await asyncio.sleep(3600)

    async def shutdown(self) -> None:
        logger.info(f"Agent '{self.name}' shutting down.")

    async def handle_greet(self, name: str = "world") -> dict:
        return {"message": f"Hello, {name}!"}

async def main():
    agent = HelloAgent(name="hello-007") # Uses HttpCommunicator by default
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Run it with `python hello_agent.py`.

For a more detailed walkthrough, see the [Getting Started Guide](https://docs.openmas.ai/guides/getting_started/).

## Contributing

Contributions are welcome! Please see the [Contributing Guide](https://docs.openmas.ai/contributing/) for details on how to get involved, set up your development environment, run tests (`tox`), and submit pull requests.

## License

OpenMAS is licensed under the [MIT License](LICENSE).
