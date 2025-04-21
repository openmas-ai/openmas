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
