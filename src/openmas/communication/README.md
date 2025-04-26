# OpenMAS Communication Module

This module provides the communication infrastructure for the OpenMAS framework, enabling agents to exchange messages using various protocols.

## Module Purpose

The communication module is responsible for:
- Abstracting different communication protocols behind a common interface
- Providing message routing between agents and services
- Handling serialization and deserialization of messages
- Managing connection lifecycles
- Supporting both request-response and notification patterns

## BaseCommunicator

The `BaseCommunicator` abstract base class defines the interface that all protocol implementations must follow. It provides the following key methods:

- `send_request`: Send a request to a target service and wait for a response
- `send_notification`: Send a one-way notification to a target service
- `register_handler`: Register a handler for a specific method
- `start`: Initialize connections and start the communicator
- `stop`: Clean up connections and stop the communicator

Any new protocol implementation must adhere to this interface to ensure compatibility with the OpenMAS framework.

## Communicator Extension System

OpenMAS provides a flexible extension system that allows developers to easily add custom communicator implementations. The extension architecture consists of:

1. **Registry Mechanism**: A central registry that maps communicator types to their implementation classes
2. **Discovery API**: Functions to look up available communicator types and retrieve their classes
3. **Configuration Integration**: Support for communicator-specific configuration options
4. **Dynamic Instantiation**: Ability to create communicator instances based on configuration

### Using the Extension System

To use a specific communicator in your agent:

```python
from openmas.agent import BaseAgent

# Configure through environment variables
# COMMUNICATOR_TYPE=mcp_stdio
# COMMUNICATOR_OPTION_SERVER_MODE=true

# Or through direct initialization
agent = BaseAgent(
    name="my-agent",
    config=AgentConfig(
        name="my-agent",
        communicator_type="http",  # or "mcp_stdio", "mcp_sse", etc.
        communicator_options={
            "server_mode": True,
            "http_port": 8000
        }
    )
)
```

### Implementing Custom Communicators

To create a custom communicator extension:

1. Implement the `BaseCommunicator` interface:

```python
from openmas.communication.base import BaseCommunicator

class MyCustomCommunicator(BaseCommunicator):
    """Custom communicator implementation."""

    def __init__(self, agent_name: str, service_urls: Dict[str, str], custom_option: str = "default"):
        super().__init__(agent_name, service_urls)
        self.custom_option = custom_option

    # Implement all required abstract methods
    async def send_request(self, target_service, method, params=None, response_model=None, timeout=None):
        # Implementation...

    async def send_notification(self, target_service, method, params=None):
        # Implementation...

    async def register_handler(self, method, handler):
        # Implementation...

    async def start(self):
        # Implementation...

    async def stop(self):
        # Implementation...
```

2. Register your communicator with the registry:

```python
from openmas.communication.base import register_communicator
from mypackage.communicator import MyCustomCommunicator

# Register the communicator type
register_communicator("my_custom", MyCustomCommunicator)
```

### Registration Methods

There are three main ways to register a custom communicator:

#### 1. Direct Registration in Code

Call `register_communicator` directly in your code, typically in your package's `__init__.py`:

```python
from openmas.communication.base import register_communicator
from mypackage.communicator import MyCustomCommunicator

register_communicator("my_custom", MyCustomCommunicator)
```

#### 2. Using Python Entry Points (Recommended)

Define entry points in your package's `pyproject.toml` or `setup.py`:

```toml
# In pyproject.toml
[project.entry-points."openmas.communicators"]
my_custom = "mypackage.communicator:MyCustomCommunicator"
```

```python
# In setup.py
setup(
    # ... other setup parameters
    entry_points={
        "openmas.communicators": [
            "my_custom=mypackage.communicator:MyCustomCommunicator",
        ],
    },
)
```

This allows OpenMAS to discover your communicator when your package is installed, without requiring explicit imports.

#### 3. Import Hook

If you prefer to register your communicator when it's imported:

```python
# In mypackage/__init__.py
from openmas.communication.base import register_communicator
from mypackage.communicator import MyCustomCommunicator

# Automatically register when package is imported
register_communicator("my_custom", MyCustomCommunicator)
```

### Extension Discovery Process

When a OpenMAS agent is initialized:

1. The agent configuration specifies a `communicator_type` (e.g., "http", "mcp_stdio", "my_custom").
2. The agent looks up the corresponding communicator class in the registry.
3. The communicator is instantiated with the agent name, service URLs, and any additional options specified in `communicator_options`.
4. The communicator's lifecycle is managed by the agent (start/stop).

## Directory Structure

```
communication/
├── __init__.py          # Module initialization and protocol registration
├── base.py              # BaseCommunicator abstract base class and extension registry
├── http.py              # HTTP protocol implementation
├── mcp/                 # Message Channel Protocol implementation
│   ├── __init__.py
│   ├── stdio_communicator.py   # MCP stdio communicator
│   └── sse_communicator.py     # MCP SSE communicator
└── README.md            # This file
```

## Implemented Protocols

### HTTP Protocol

The HTTP protocol implementation (`http.py`) provides communication over HTTP, making it suitable for distributed agents running on different machines or in different processes. It uses JSON-RPC over HTTP for message formatting.

For details, see the [HTTP Protocol Documentation](../../docs/communication.md#http-communication).

### Message Channel Protocol (MCP)

The Message Channel Protocol implementation (`mcp/`) provides high-performance in-memory communication for agents running in the same process. It's optimized for low-latency, high-throughput communication between LLM-based agents.

For details, see the [MCP Documentation](../../docs/communication.md#message-channel-protocol-mcp).

## Best Practices for Extension Developers

1. **Clear Documentation**: Document your communicator's configuration options, constraints, and use cases.
2. **Comprehensive Testing**: Thoroughly test your communicator in isolation and integrated with OpenMAS.
3. **Error Handling**: Implement proper error handling and provide clear error messages.
4. **Resource Management**: Ensure proper cleanup in the `stop()` method to prevent resource leaks.
5. **Configuration**: Design your communicator to accept configuration options through `communicator_options`.
6. **Compatibility**: Only advertise compatibility with OpenMAS versions you've tested against.

## For Developers

When implementing a new protocol:

1. Create a new file or package for your protocol implementation
2. Extend `BaseCommunicator` and implement all required methods
3. Add appropriate error handling and logging
4. Write comprehensive tests for your implementation
5. Update the module's `__init__.py` to expose your implementation
6. Document your protocol in the user-facing documentation

See the existing protocol implementations for reference.
