# SimpleMAS

A lightweight SDK for building Multi-Agent Systems with a focus on the Model Context Protocol (MCP).

## Features

- **Agent Framework** - Build autonomous agents with the BaseAgent class and extension points
- **Rich Communication Options** - HTTP, WebSockets, gRPC, and MCP-based communication between agents
- **Model Context Protocol (MCP) Integration** - First-class support for Anthropic's MCP
- **Environment-based Configuration** - Configure agents using environment variables
- **Belief-Desire-Intention (BDI) Patterns** - Build agents that reason about beliefs, desires, and intentions
- **Testing Framework** - Test your agents with the built-in testing framework
- **Deployment Tools** - Generate and orchestrate deployment configurations for Docker Compose and Kubernetes

## Installation

```bash
pip install simple-mas
```

Or with Poetry:

```bash
poetry add simple-mas
```

## Usage

### Basic Agent

```python
from simple_mas.agent import BaseAgent
from simple_mas.communication import HTTPCommunicator

class MyAgent(BaseAgent):
    async def setup(self) -> None:
        # Initialize your agent here
        self.communicator = HTTPCommunicator(
            agent_name=self.name,
            service_urls={"other-agent": "http://other-agent:8000/"}
        )

    async def run(self) -> None:
        # Run your agent's main logic
        response = await self.communicator.send_request(
            "other-agent",
            "get_data",
            {"query": "example"}
        )

    async def shutdown(self) -> None:
        # Clean up resources
        pass

# Run the agent
async def main():
    agent = MyAgent(name="my-agent")
    await agent.start()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### MCP Integration

SimpleMAS provides first-class support for the Model Context Protocol (MCP):

```python
from simple_mas.agent import BaseAgent
from simple_mas.communication.mcp import McpSseCommunicator
from mcp.client.session import ClientSession
from mcp.types import TextContent

class McpAgent(BaseAgent):
    async def setup(self) -> None:
        self.communicator = McpSseCommunicator(
            agent_name=self.name,
            service_urls={"mcp-service": "http://mcp-service:8000/"}
        )

    async def run(self) -> None:
        content = TextContent(text="What's the meaning of life?")
        response = await self.communicator.send_request(
            "mcp-service",
            "process",
            {"content": content}
        )
```

### CLI Tool

SimpleMAS includes a command-line tool for managing your multi-agent systems:

```bash
# Generate deployment configurations
simplemas deploy --directory ./my-project --output ./deployment

# Run quality checks
simplemas check

# Start a local agent
simplemas run --agent my-agent
```

## Documentation

For more details, see the [documentation](docs/):

- [Getting Started](docs/getting_started.md)
- [Architecture](docs/architecture.md)
- [Communication](docs/communication.md)
- [Deployment](docs/deployment.md)
- [Testing](docs/testing.md)
- [MCP Integration](docs/mcp_integration.md)
- [Patterns](docs/patterns.md)

## Quick Start

```python
from simple_mas.agent import BaseAgent
from simple_mas.communication.mcp import McpSseCommunicator

class MyAgent(BaseAgent):
    async def setup(self) -> None:
        # Initialize your agent with MCP communication
        self.communicator = McpSseCommunicator(
            agent_name=self.name,
            service_urls={"assistant": "http://assistant-service:8000/"}
        )

    async def run(self) -> None:
        # Send a request to the assistant service
        response = await self.communicator.send_request(
            "assistant",
            "generate_response",
            {"prompt": "Tell me about multi-agent systems"}
        )
        print(f"Response: {response}")

    async def shutdown(self) -> None:
        # Clean up resources
        await self.communicator.close()

# Run the agent
async def main():
    agent = MyAgent(name="my-agent")
    await agent.start()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Development

```bash
# Clone the repository
git clone https://github.com/yourusername/simple-mas.git
cd simple-mas

# Install dependencies
poetry install

# Install pre-commit hooks
poetry run pre-commit install

# Run tests
poetry run pytest

# Run type checking
poetry run mypy --config-file=mypy.ini src tests

# Run all code quality checks at once
poetry run pre-commit run --all-files
```

### Code Quality

This project uses several tools to ensure code quality:

- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing

Pre-commit hooks are configured to run these checks automatically before each commit.

## License

MIT
