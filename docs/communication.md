# Communication in SimpleMas

This document provides an overview of the communication protocols in SimpleMas, explaining when and how to use each one.

## Communication Overview

SimpleMas provides a flexible communication layer that abstracts away the complexity of different communication protocols. The core of this system is the `BaseCommunicator` interface, which all protocol implementations extend.

## Available Protocols

### HTTP Communication

The HTTP protocol implementation uses standard HTTP requests for communication between agents and services. It's suitable for:
- RESTful API interactions
- Web-based service integration
- Scenarios where agents run in different processes or machines

**Configuration Example:**
```python
from simple_mas.communication import HTTPCommunicator

communicator = HTTPCommunicator(
    agent_name="agent1",
    service_urls={
        "service1": "http://localhost:8000/service1",
        "service2": "http://localhost:8001/service2"
    }
)
```

### Message Channel Protocol (MCP)

The Message Channel Protocol is optimized for high-performance, in-memory communication. It's ideal for:
- Agents running in the same process
- High-frequency message passing
- Testing and development

**Configuration Example:**
```python
from simple_mas.communication.mcp import MCPCommunicator

communicator = MCPCommunicator(
    agent_name="agent1",
    service_urls={
        "service1": "mcp://service1",
        "service2": "mcp://service2"
    }
)
```

## When to Use Each Protocol

| Protocol | Best For | Limitations |
|----------|----------|-------------|
| HTTP | Cross-process/cross-machine communication | Higher latency, network dependency |
| MCP | Same-process communication, high performance | Limited to single process |

## Extending with Custom Protocols

SimpleMas allows you to create custom protocol implementations by extending the `BaseCommunicator` class. See the developer documentation for details on implementing your own communicator.
