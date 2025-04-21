# SimpleMAS Architecture

## Overview

SimpleMAS is a lightweight SDK for building Multi-Agent Systems (MAS) with a focus on the Model Context Protocol (MCP). It provides a simple, composable foundation for building agents that can communicate with each other and with external services.

## Core Components

### 1. BaseAgent

The `BaseAgent` class is the foundation of all agents in SimpleMAS. It provides:

- Configuration loading and validation
- Communication setup
- Lifecycle management (setup, run, shutdown)
- Error handling and logging

Developers extend this class to create their own agents, implementing the abstract methods:

```python
async def setup(self) -> None: ...
async def run(self) -> None: ...
async def shutdown(self) -> None: ...
```

### 2. Configuration System

The configuration system uses Pydantic models to validate configuration values:

- `AgentConfig` is the base configuration model
- Environment variables are the primary source of configuration
- Support for JSON configuration strings
- Prefixed environment variables for multiple agents

### 3. Communication System

The communication system is based on a pluggable architecture:

- `BaseCommunicator` defines the interface for all communicators
- `HttpCommunicator` provides basic HTTP JSON-RPC communication
- `McpBaseCommunicator` implements common MCP functionality
- `McpSseCommunicator` implements MCP over HTTP+SSE
- `McpStdioCommunicator` implements MCP over stdio

Each communicator provides methods for:

- Sending requests and notifications
- Registering handlers for incoming messages
- Managing connections to services

### 4. Logging System

The logging system is based on structlog:

- Structured JSON logs
- Contextual logging with metadata
- Support for different output formats
- Configurable log levels

## Usage Patterns

### Basic Agent

```python
class MyAgent(BaseAgent):
    async def setup(self) -> None:
        # Initialize resources, register handlers
        pass

    async def run(self) -> None:
        # Main agent logic
        while True:
            # Do something
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        # Clean up resources
        pass
```

### MCP Server Agent

```python
class MyMcpServer(BaseAgent):
    async def setup(self) -> None:
        # Register MCP handlers
        await self.communicator.register_handler("list_resources", self.handle_list_resources)
        await self.communicator.register_handler("get_resource", self.handle_get_resource)

    async def run(self) -> None:
        # For MCP servers, we typically just wait for requests
        await asyncio.sleep(float("inf"))

    async def handle_list_resources(self, params):
        # Return list of resources
        return {"resources": [...]}
```

### MCP Client Agent

```python
class MyMcpClient(BaseAgent):
    async def run(self) -> None:
        # Send requests to MCP servers
        response = await self.communicator.send_request(
            "mcp-server",
            "get_resource",
            {"uri": "example://resource"}
        )
```

## Extension Points

SimpleMAS is designed to be extended in several ways:

1. **Custom Agents**: Extend `BaseAgent` to create new types of agents
2. **Custom Communicators**: Implement `BaseCommunicator` for new protocols
3. **Custom Configurations**: Extend `AgentConfig` for agent-specific settings

## Runtime Environment

SimpleMAS agents can run in various environments:

- As standalone processes
- In containers (Docker, Kubernetes)
- As serverless functions
- In development environments

## Deployment

The examples include a Docker Compose setup that demonstrates:

- Running multiple agents
- Inter-agent communication
- Environment configuration

## Future Considerations

1. **Full MCP Support**: More complete implementation of the MCP specification
2. **Advanced Orchestration**: Support for more complex agent interaction patterns
3. **Deployment Aids**: Tools for generating deployment configurations
4. **Reasoning Models**: Integration with reasoning frameworks (BDI, etc.)
5. **Scaling**: Support for horizontal scaling of agents
