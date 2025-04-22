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
- Integration with AI models and tools via Anthropic's MCP

SimpleMas provides specialized MCP communicator implementations:

#### MCP Stdio Communicator

Specifically designed for MCP communication over standard input/output. Can operate in both client and server roles.

**Client Mode Example:**
```python
from simple_mas.communication.mcp import McpStdioCommunicator

communicator = McpStdioCommunicator(
    agent_name="agent1",
    service_urls={
        "mcp_service": "python -m service_script.py"  # Command to run the MCP service
    }
)
```

**Server Mode Example:**
```python
from simple_mas.communication.mcp import McpStdioCommunicator

communicator = McpStdioCommunicator(
    agent_name="agent1",
    service_urls={},  # Not used in server mode
    server_mode=True,
    server_instructions="This agent provides analysis tools."
)
```

#### MCP SSE Communicator

Uses HTTP with Server-Sent Events for MCP communication. Can operate in both client and server roles.

**Client Mode Example:**
```python
from simple_mas.communication.mcp import McpSseCommunicator

communicator = McpSseCommunicator(
    agent_name="agent1",
    service_urls={
        "mcp_service": "http://localhost:8000/mcp"  # URL of the MCP service
    }
)
```

**Server Mode Example:**
```python
from fastapi import FastAPI
from simple_mas.communication.mcp import McpSseCommunicator

# Optional: Create a FastAPI app (will create one if not provided)
app = FastAPI(title="MCP Agent")

communicator = McpSseCommunicator(
    agent_name="agent1",
    service_urls={},  # Not used in server mode
    server_mode=True,
    http_port=8000,
    server_instructions="This agent provides analysis tools.",
    app=app  # Optional
)
```

## When to Use Each Protocol

| Protocol | Best For | Limitations |
|----------|----------|-------------|
| HTTP | Cross-process/cross-machine communication | Higher latency, network dependency |
| MCP Stdio | MCP with subprocess or CLI | Requires subprocess management |
| MCP SSE | MCP with web services | Requires HTTP infrastructure |

## When to Use Each MCP Communicator

| Communicator | Client Mode | Server Mode | Best For |
|--------------|-------------|------------|----------|
| McpStdioCommunicator | Spawn and connect to subprocess MCP services | Run as MCP server via stdin/stdout | CLI tools, subprocess integration |
| McpSseCommunicator | Connect to HTTP-based MCP services | Run as HTTP/SSE MCP server | Web services, UI integration, API gateway patterns |

## MCP Method Mapping

SimpleMas's request/response model maps to MCP's tool/prompt/resource model as follows:

| SimpleMas Method | MCP Equivalent |
|------------------|---------------|
| `send_request("service", "tool/list")` | `list_tools()` |
| `send_request("service", "tool/call", {"name": "tool_name", "arguments": {...}})` | `call_tool("tool_name", {...})` |
| `send_request("service", "prompt/list")` | `list_prompts()` |
| `send_request("service", "prompt/get", {"name": "prompt_name", "arguments": {...}})` | `get_prompt("prompt_name", {...})` |
| `send_request("service", "resource/list")` | `list_resources()` |
| `send_request("service", "resource/read", {"uri": "resource_uri"})` | `read_resource("resource_uri")` |
| `send_request("service", "custom_method", {...})` | `call_tool("custom_method", {...})` |
| `send_notification("service", "method", {...})` | Async `call_tool("method", {...})` |

## Extending with Custom Protocols

SimpleMas allows you to create custom protocol implementations by extending the `BaseCommunicator` class. See the developer documentation for details on implementing your own communicator.
