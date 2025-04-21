# SimpleMAS

A lightweight SDK for building Multi-Agent Systems with a focus on the Model Context Protocol (MCP).

## Features

- Simplified agent structure with configuration management
- Pluggable communication backends (MCP over SSE and Stdio)
- Standardized error handling and logging
- Reduced boilerplate for creating MCP servers and clients

## Installation

```bash
pip install simple-mas
```

Or with Poetry:

```bash
poetry add simple-mas
```

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
