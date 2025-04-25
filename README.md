# OpenMAS

A lightweight SDK for building Multi-Agent Systems with a focus on the Model Context Protocol (MCP).

## Features

- **Agent Framework** - Build autonomous agents with the BaseAgent class and extension points
- **Rich Communication Options** - HTTP, WebSockets, gRPC, and MCP-based communication between agents
- **Model Context Protocol (MCP) Integration** - First-class support for Anthropic's MCP
- **Environment-based Configuration** - Configure agents using environment variables
- **Belief-Desire-Intention (BDI) Patterns** - Build agents that reason about beliefs, desires, and intentions
- **Testing Framework** - Test your agents with the built-in testing framework
- **Deployment Tools** - Generate and orchestrate deployment configurations for Docker Compose and Kubernetes
- **Package Management** - Import dependencies from Git repositories with `openmas deps`

## Installation

```bash
pip install openmas
```

Or with Poetry:

```bash
poetry add openmas
```

### Optional Dependencies

OpenMAS has a modular design with optional dependencies for different communication protocols. The core package is lightweight, and you can install only the dependencies you need:

```bash
# Install MCP support (Anthropic Model Context Protocol)
pip install 'openmas[mcp]'

# Install gRPC support
pip install 'openmas[grpc]'

# Install MQTT support
pip install 'openmas[mqtt]'

# Install all optional dependencies
pip install 'openmas[all]'
```

With Poetry:

```bash
# Install MCP support
poetry add 'openmas[mcp]'

# Install multiple optional dependencies
poetry add 'openmas[mcp,grpc,mqtt]'
```

## Usage

### Basic Agent

```python
from openmas.agent import BaseAgent
from openmas.communication import HTTPCommunicator

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

### Package Management

OpenMAS provides Git-based package management inspired by dbt. Define dependencies in your `openmas_project.yml`:

```yaml
dependencies:
  - git: https://github.com/example/openmas-repo.git
    revision: main
```

Install dependencies:

```bash
openmas deps
```

Learn more in the [package management documentation](docs/cli/deps.md).

## Development

```bash
# Clone the repository
git clone https://github.com/yourusername/openmas.git
cd openmas

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
