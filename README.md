# SimpleMAS

A lightweight SDK for building Multi-Agent Systems with a focus on the Model Context Protocol (MCP).

## Features

- **Agent communication** - HTTP, WebSockets, and MCP-based communication between agents
- **Environment-based configuration** - Configure agents using environment variables
- **Belief-Desire-Intention (BDI) agents** - Build agents that reason about beliefs, desires, and intentions
- **Reasoning integration** - Easily integrate LLMs and other reasoning systems
- **Deployment tools** - Generate and orchestrate deployment configurations for Docker Compose and Kubernetes

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
from simple_mas import Agent
from simple_mas.communication import HTTPCommunicator

agent = Agent(
    name="my-agent",
    communicator=HTTPCommunicator(
        agent_name="my-agent",
        service_urls={"other-agent": "http://other-agent:8000/"}
    )
)

# Add capabilities, start the agent, etc.
```

### Deployment Orchestration

SimpleMas includes powerful tools for deploying multi-agent systems:

```bash
# Discover SimpleMas components in your project
simplemas discover --directory ./my-project

# Orchestrate components into a single Docker Compose file
simplemas orchestrate --directory ./my-project --output docker-compose.yml

# Generate Kubernetes manifests for a component
simplemas k8s --input ./my-project/agent/simplemas.deploy.yaml --output k8s/
```

## Documentation

For more details, see the [documentation](docs/).

## Quick Start

```python
from simple_mas.agent import BaseAgent
from simple_mas.communication import McpSseCommunicator

class MyAgent(BaseAgent):
    async def setup(self) -> None:
        # Initialize your agent here
        pass

    async def run(self) -> None:
        # Run your agent's main logic
        response = await self.communicator.send_request(
            "chess-engine",
            "make_move",
            {"board_state": "..."}
        )

    async def shutdown(self) -> None:
        # Clean up resources
        pass

# Run the agent
async def main():
    agent = MyAgent(name="my-orchestrator")
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

# Run all code quality checks at once
./scripts/check_quality.sh

# Or run individual checks
poetry run black src tests
poetry run isort src tests
poetry run flake8 src tests
poetry run mypy src
```

### Code Quality

This project uses several tools to ensure code quality:

- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing

Pre-commit hooks are configured to run these checks automatically before each commit.
You can also run all checks manually using the `./scripts/check_quality.sh` script.

## License

MIT
