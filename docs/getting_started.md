# Getting Started with SimpleMas

This guide will help you get started with SimpleMas, the Python SDK for building Multi-Agent Systems.

## Installation

Install SimpleMas using poetry:

```bash
poetry add simple-mas
```

Or using pip:

```bash
pip install simple-mas
```

## Quick Start

```python
from simple_mas import Agent
from simple_mas.communication import HTTPCommunicator

# Create an agent with HTTP communication
agent = Agent(
    name="my_agent",
    communicator=HTTPCommunicator(
        agent_name="my_agent",
        service_urls={"target_service": "http://localhost:8000/service"}
    )
)

# Define a handler for incoming messages
@agent.handler("greet")
async def handle_greet(params):
    return {"message": f"Hello from {agent.name}!"}

# Start the agent
await agent.start()

# Send a request to another service
response = await agent.send_request(
    target_service="target_service",
    method="get_data",
    params={"query": "example"}
)

# Stop the agent when done
await agent.stop()
```

## Next Steps

- Learn about [SimpleMas Architecture](architecture.md)
- Explore [Communication Protocols](communication.md)
- See [Common Patterns](patterns.md) for multi-agent systems




# Getting Started with SimpleMAS

This guide will help you get started with SimpleMAS, a lightweight SDK for building Multi-Agent Systems.

## Installation

Install SimpleMAS using pip:

```bash
pip install simple-mas
```

Or with Poetry:

```bash
poetry add simple-mas
```

## Creating Your First Agent

Let's create a simple agent that responds to HTTP requests:

```python
import asyncio
from simple_mas.agent import BaseAgent
from simple_mas.logging import configure_logging, get_logger

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

SimpleMAS uses environment variables for configuration:

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
from simple_mas.config import AgentConfig

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

SimpleMAS supports different communication protocols. Here's how to use them:

### HTTP Communicator (Default)

```python
from simple_mas.communication import HttpCommunicator

agent = MyAgent(communicator_class=HttpCommunicator)
```

### MCP SSE Communicator

```python
from simple_mas.communication import McpSseCommunicator

agent = MyAgent(communicator_class=McpSseCommunicator)
```

### MCP Stdio Communicator

```python
from simple_mas.communication import McpStdioCommunicator

agent = MyAgent(communicator_class=McpStdioCommunicator)
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

RUN pip install simple-mas

COPY my_first_agent.py .

CMD ["python", "my_first_agent.py"]
```

Build and run:

```bash
docker build -t my-agent .
docker run -p 8000:8000 -e AGENT_NAME=my-agent my-agent
```

## Next Steps

1. Check out the example agents in the `examples/` directory
2. Read the Architecture document for a deeper understanding
3. Explore the MCP communication examples
4. Try creating agents that communicate with each other
