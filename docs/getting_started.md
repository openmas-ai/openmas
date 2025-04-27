# Getting Started with OpenMAS

This guide will help you get started with OpenMAS, a lightweight SDK for building Multi-Agent Systems.

## Installation

### Basic Installation

Install OpenMAS using pip:

```bash
pip install openmas
```

Or with Poetry:

```bash
poetry add openmas
```

### Installing with Optional Dependencies

OpenMAS supports various communication protocols through optional dependencies. You can install them using "extras":

#### Model Context Protocol (MCP)

For integration with Anthropic's MCP:

```bash
pip install openmas[mcp]
```

With Poetry:

```bash
poetry add "openmas[mcp]"
```

#### gRPC Support

For agents that communicate via gRPC:

```bash
pip install openmas[grpc]
```

With Poetry:

```bash
poetry add "openmas[grpc]"
```

#### MQTT Support

For agents that communicate via MQTT:

```bash
pip install openmas[mqtt]
```

With Poetry:

```bash
poetry add "openmas[mqtt]"
```

#### All Optional Dependencies

To install all optional dependencies at once:

```bash
pip install openmas[all]
```

With Poetry:

```bash
poetry add "openmas[all]"
```

## Creating Your First Agent

Let's create a simple agent that responds to HTTP requests:

```python
import asyncio
from openmas.agent import BaseAgent
from openmas.logging import configure_logging, get_logger

logger = get_logger(__name__)

class MyFirstAgent(BaseAgent):
    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up my first agent")

        # Register a handler for the "greet" method
        await self.communicator.register_handler("greet", self.handle_greet)

    async def run(self) -> None:
        """Run the agent."""
        logger.info("My first agent is running")

        # Keep the agent running
        await asyncio.sleep(float("inf"))

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("Shutting down my first agent")

    async def handle_greet(self, params):
        """Handle a greeting request."""
        name = params.get("name", "world")
        logger.info(f"Received greeting request for {name}")

        return {
            "message": f"Hello, {name}!"
        }

async def main():
    # Configure logging
    configure_logging(log_level="INFO")

    # Create and start the agent
    agent = MyFirstAgent(name="my-first-agent")

    try:
        await agent.start()

        # Keep the main function running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Save this to a file named `my_first_agent.py` and run it:

```bash
python my_first_agent.py
```

## Configuration

OpenMAS uses environment variables for configuration:

```bash
# Set the agent name
export AGENT_NAME="my-agent"

# Set the log level
export LOG_LEVEL="DEBUG"

# Configure service URLs
export SERVICE_URL_OTHER_AGENT="http://localhost:8000"
```

Or you can pass configuration directly in code:

```python
from openmas.config import AgentConfig

config = AgentConfig(
    name="my-agent",
    log_level="DEBUG",
    service_urls={
        "other-agent": "http://localhost:8000"
    }
)

agent = MyAgent(config=config)
```

## Using Different Communicators

OpenMAS supports different communication protocols. Here's how to use them:

### HTTP Communicator (Default)

```python
from openmas.communication import HttpCommunicator

agent = MyAgent(communicator_class=HttpCommunicator)
```

### MCP SSE Communicator

Requires the MCP extra: `pip install openmas[mcp]`

```python
from openmas.communication.mcp import McpSseCommunicator

agent = MyAgent(communicator_class=McpSseCommunicator)
```

### MCP Stdio Communicator

Requires the MCP extra: `pip install openmas[mcp]`

```python
from openmas.communication.mcp import McpStdioCommunicator

agent = MyAgent(communicator_class=McpStdioCommunicator)
```

### gRPC Communicator

Requires the gRPC extra: `pip install openmas[grpc]`

```python
from openmas.communication.grpc import GrpcCommunicator

agent = MyAgent(communicator_class=GrpcCommunicator)
```

### MQTT Communicator

Requires the MQTT extra: `pip install openmas[mqtt]`

```python
from openmas.communication.mqtt import MqttCommunicator

agent = MyAgent(communicator_class=MqttCommunicator)
```

## Extending BaseAgent

You can extend `BaseAgent` to create custom agent types with additional functionality:

```python
class MyCustomAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_state = {}

    async def setup(self) -> None:
        await super().setup()
        # Additional setup code

    async def custom_method(self):
        # Custom functionality
        pass
```

## Running in Docker

Create a Dockerfile:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN pip install openmas[mcp]  # Include any extras you need

COPY my_first_agent.py .

CMD ["python", "my_first_agent.py"]
```

Build and run:

```bash
docker build -t my-agent .
docker run -p 8000:8000 -e AGENT_NAME=my-agent my-agent
```

## Using the CLI

OpenMAS provides a command-line interface for managing projects:

```bash
# Initialize a new project
openmas init my_project

# Run an agent from a project
openmas run my_agent

# Validate a project configuration
openmas validate
```

See the [CLI documentation](./cli/index.md) for more details.

## Next Steps

1. Check out the example agents in the `examples/` directory
2. Read the [Architecture](./architecture.md) document for a deeper understanding
3. Explore the [MCP Integration](./mcp_integration.md) documentation
4. Learn about [Testing](./testing.md) your agents
5. Understand the [Configuration](./configuration.md) system
