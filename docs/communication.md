# Communication in OpenMAS

This document provides an overview of the communication protocols in OpenMAS, explaining when and how to use each one.

## Communication Overview

OpenMAS provides a flexible communication layer that abstracts away the complexity of different communication protocols. The core of this system is the `BaseCommunicator` interface, which all protocol implementations extend.

## Available Protocols

### HTTP Communication

The HTTP protocol implementation uses standard HTTP requests for communication between agents and services. It's suitable for:
- RESTful API interactions
- Web-based service integration
- Scenarios where agents run in different processes or machines

**Configuration Example:**
```python
from openmas.communication import HTTPCommunicator

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

OpenMAS provides specialized MCP communicator implementations:

#### MCP Stdio Communicator

Specifically designed for MCP communication over standard input/output. Can operate in both client and server roles.

**Client Mode Example - Connecting to an External MCP Server:**
```python
from openmas.communication.mcp import McpStdioCommunicator

communicator = McpStdioCommunicator(
    agent_name="agent1",
    service_urls={
        "local_service": "python -m service_script.py",  # Command to run a local MCP service
        "external_service": "stdio:/path/to/external/executable"  # Connection to external executable
    }
)
```

**Server Mode Example:**
```python
from openmas.communication.mcp import McpStdioCommunicator

communicator = McpStdioCommunicator(
    agent_name="agent1",
    service_urls={},  # Not used in server mode
    server_mode=True,
    server_instructions="This agent provides analysis tools."
)
```

#### MCP SSE Communicator

Uses HTTP with Server-Sent Events for MCP communication. Can operate in both client and server roles.

**Client Mode Example - Connecting to External MCP Servers:**
```python
from openmas.communication.mcp import McpSseCommunicator

communicator = McpSseCommunicator(
    agent_name="agent1",
    service_urls={
        "local_service": "http://localhost:8000/mcp",  # Local MCP service
        "external_service": "http://external-server.example.com:8080"  # External MCP server
    }
)
```

**Server Mode Example:**
```python
from fastapi import FastAPI
from openmas.communication.mcp import McpSseCommunicator

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
| McpStdioCommunicator | Spawn and connect to subprocess MCP services or external executables | Run as MCP server via stdin/stdout | CLI tools, subprocess integration, connecting to existing MCP tools like Stockfish |
| McpSseCommunicator | Connect to HTTP-based MCP services (local or external) | Run as HTTP/SSE MCP server | Web services, UI integration, API gateway patterns, connecting to cloud-based MCP services |

## Connecting to External MCP Servers

OpenMAS supports connecting to external MCP servers in both stdio and SSE modes:

### Stdio Connection Format

For stdio connections to external executables, use the `stdio:` protocol prefix:

```python
service_urls = {
    "stockfish": "stdio:/usr/local/bin/stockfish",  # Path to Stockfish executable
    "custom_tool": "stdio:/path/to/custom/tool"     # Path to any MCP-compatible executable
}
```

When using the stdio protocol prefix, OpenMAS will execute the specified binary and communicate with it via stdin/stdout.

### SSE Connection Format

For SSE connections to external HTTP-based MCP servers, use standard HTTP URLs:

```python
service_urls = {
    "local_service": "http://localhost:8000",              # Local MCP server
    "cloud_service": "https://api.example.com/mcp-server"  # External cloud MCP server
}
```

## MCP Method Mapping

When an OpenMAS agent uses an MCP communicator (`McpSseCommunicator` or `McpStdioCommunicator`) in *client mode* to interact with a remote MCP server, the standard OpenMAS communicator methods (`send_request`, `send_notification`) are mapped to the underlying MCP protocol actions on the remote server:

| Your Agent's Call (`self.communicator.<method>`) | Remote MCP Action Triggered | Description |
|----------------------------------------------------|-----------------------------|-------------|
| `send_request(target_service="svc", method="tool/list")` | `list_tools()` | Lists tools on the remote MCP server `svc`. |
| `send_request(target_service="svc", method="tool/call", params={"name": "calc", "arguments": {"a":1}})` | `call_tool("calc", {"a":1})` | Calls the tool named "calc" on the remote server `svc`. |
| `send_request(target_service="svc", method="prompt/list")` | `list_prompts()` | Lists prompts on the remote server `svc`. |
| `send_request(target_service="svc", method="prompt/get", params={"name": "qa", "arguments": {"q":"Hi"}})` | `get_prompt("qa", {"q":"Hi"})` | Gets the prompt named "qa" from the remote server `svc`. |
| `send_request(target_service="svc", method="resource/list")` | `list_resources()` | Lists resources on the remote server `svc`. |
| `send_request(target_service="svc", method="resource/read", params={"uri": "/data.json"})` | `read_resource("/data.json")` | Reads the resource at the specified URI from server `svc`. |
| `send_request(target_service="svc", method="some_custom_name", params={...})` | `call_tool("some_custom_name", {...})` | By convention, non-prefixed methods often map to `call_tool` on the server. |
| `send_notification(target_service="svc", method="log_event", params={...})` | Async `call_tool("log_event", {...})` | Sends a notification, often mapped to an asynchronous tool call on the server `svc` where no response is expected by the caller. |

**Note:** This mapping applies when your OpenMAS agent is acting as an *MCP client*. When your agent acts as an *MCP server* (using `MCPServerAgent` or a communicator in `server_mode=True`), incoming MCP requests trigger the methods decorated with `@mcp_tool`, `@mcp_prompt`, or `@mcp_resource` within your agent.

## Extending with Custom Protocols

OpenMAS allows you to create custom protocol implementations by extending the `BaseCommunicator` class. See the developer documentation for details on implementing your own communicator.

## Communicator Extension System

OpenMAS includes an extension system that allows developers to create and register their own communicator implementations. This system enables easy extension of OpenMAS with custom communication protocols.

### Using the Extension System

The communicator extension system allows users to specify a communicator type in their agent configuration:

```python
from openmas.agent import BaseAgent
from openmas.config import AgentConfig

# Configure through environment variables
# COMMUNICATOR_TYPE=mcp_stdio
# COMMUNICATOR_OPTION_SERVER_MODE=true

# Or through direct initialization with config
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

# Or just override the communicator class directly
from openmas.communication import HttpCommunicator
agent = BaseAgent(
    name="my-agent",
    communicator_class=HttpCommunicator
)
```

### Available Configuration Options

#### HTTP Communicator

| Option | Default | Description |
|--------|---------|-------------|
| None currently | | |

#### MCP Stdio Communicator

| Option | Default | Description |
|--------|---------|-------------|
| `server_mode` | `False` | Whether to run in server mode |
| `server_instructions` | `None` | Instructions for the server |

#### MCP SSE Communicator

| Option | Default | Description |
|--------|---------|-------------|
| `server_mode` | `False` | Whether to run in server mode |
| `http_port` | `8000` | Port for the HTTP server (server mode only) |
| `server_instructions` | `None` | Instructions for the server |

#### gRPC Communicator

| Option | Default | Description |
|--------|---------|-------------|
| `server_mode` | `False` | Whether to run in server mode |
| `server_address` | `[::]:50051` | Address to bind the server to (server mode only) |
| `max_workers` | `10` | Maximum number of server worker threads |
| `channel_options` | `{}` | Additional gRPC channel options |

### gRPC Communication

The gRPC communicator provides efficient, high-performance communication using Google's gRPC framework. It requires the `openmas[grpc]` extra to be installed.

It's suitable for:

- High-performance, type-safe communication (if using Protobuf definitions)
- Cross-language interoperability
- Streaming scenarios
- Microservice architectures where gRPC is already in use

**Configuration Example (Client Mode):**

```python
# In config (e.g., YAML or environment variables)
# COMMUNICATOR_TYPE=grpc
# SERVICE_URL_MY_GRPC_SERVICE=localhost:50051

from openmas.communication.grpc import GrpcCommunicator

# Or instantiated directly:
communicator = GrpcCommunicator(
    agent_name="my-grpc-client",
    service_urls={
        "my_grpc_service": "localhost:50051" # Address of the target gRPC server
    },
    # server_mode=False # Default
)
```

**Configuration Example (Server Mode):**

```python
# In config:
# COMMUNICATOR_TYPE=grpc
# COMMUNICATOR_OPTION_SERVER_MODE=true
# COMMUNICATOR_OPTION_GRPC_PORT=50052

from openmas.communication.grpc import GrpcCommunicator

# Or instantiated directly:
communicator = GrpcCommunicator(
    agent_name="my-grpc-server",
    service_urls={}, # Not needed for server
    server_mode=True,
    grpc_port=50052 # Port for this agent's gRPC server to listen on
)
```

**Note:** The current `GrpcCommunicator` uses a generic dictionary-based request/response format over gRPC. For type safety using Protobuf definitions, you would typically implement a custom communicator or extend the existing one.

### MQTT Communication

The MQTT communicator uses the MQTT protocol for publish/subscribe messaging, typically via an MQTT broker. It requires the `openmas[mqtt]` extra.

It's suitable for:

- Event-driven architectures
- Decoupled communication where agents publish or subscribe to topics
- IoT scenarios
- Situations where a message broker is preferred

**Configuration Example:**

```python
# In config:
# COMMUNICATOR_TYPE=mqtt
# COMMUNICATOR_OPTION_BROKER_HOST=mqtt.eclipseprojects.io
# COMMUNICATOR_OPTION_BROKER_PORT=1883
# SERVICE_URLS={} # Often not used directly, communication is via pub/sub

from openmas.communication.mqtt import MqttCommunicator

# Or instantiated directly:
communicator = MqttCommunicator(
    agent_name="my-mqtt-agent",
    service_urls={}, # Agents typically discover each other via topics
    broker_host="mqtt.eclipseprojects.io", # Address of the MQTT broker
    broker_port=1883,
    # Optional: username="user", password="pass", client_id="custom_id"
)
```

**Note:** With MQTT, agents usually communicate via topics rather than direct service names in `service_urls`. The `send_request` and `send_notification` methods in the `MqttCommunicator` likely map `target_service` and `method` to specific MQTT topics based on internal conventions.

### MQTT Communicator

| Option | Default | Description |
|--------|---------|-------------|
| `broker_host` | `"localhost"` | Hostname or IP address of the MQTT broker. |
| `broker_port` | `1883` | Port of the MQTT broker. |
| `username` | `None` | Username for MQTT broker authentication. |
| `password` | `None` | Password for MQTT broker authentication. |
| `client_id` | Auto-generated | MQTT client ID. If empty, one is generated. |
| `keepalive` | `60` | MQTT keepalive interval in seconds. |
| `tls_enabled` | `False` | Enable TLS/SSL encryption. |
| `tls_ca_certs` | `None` | Path to CA certificate file for TLS. |
| `tls_certfile` | `None` | Path to client certificate file for TLS. |
| `tls_keyfile` | `None` | Path to client private key file for TLS. |
