# Communication in OpenMAS

This document provides an overview of the communication protocols in OpenMAS, explaining when and how to use each one.

## Communication Overview

OpenMAS provides a flexible communication layer that abstracts away the complexity of different communication protocols. The core of this system is the `BaseCommunicator` abstract base class, which defines the standard interface for sending requests (`send_request`), sending notifications (`send_notification`), and registering handlers for incoming messages (`register_handler`). All specific protocol implementations (like `HttpCommunicator`, `McpSseCommunicator`, etc.) inherit from `BaseCommunicator`.

An agent's communicator is typically instantiated automatically by `BaseAgent` based on the `communicator_type` and `communicator_options` specified in the agent's configuration.

## Lazy Loading of Communicators

A key design principle in OpenMAS is **lazy loading** for optional components, especially communicators that require extra dependencies.

* **Core vs. Optional:** The `HttpCommunicator` (using `httpx`) might be considered core or have minimal dependencies. Communicators for MCP (`mcp`), gRPC (`grpcio`), and MQTT (`paho-mqtt`) require specific third-party libraries.
* **Mechanism:** OpenMAS does *not* require you to install all possible communication libraries just to use the core framework. When `BaseAgent` initializes, it looks at the configured `communicator_type`. If it's a non-core type (e.g., "grpc", "mcp_sse", "mqtt"), the framework attempts to dynamically import the necessary communicator class (`GrpcCommunicator`, `McpSseCommunicator`, etc.) using `importlib`.
* **Dependency Management:** If the import fails because the required underlying library (e.g., `grpcio` for `GrpcCommunicator`) is not installed in your environment, OpenMAS will raise an `ImportError` or a specific `ConfigurationError` guiding you to install the necessary optional dependency.
* **Installation:** You install support for optional communicators using pip extras:
    ```bash
    # Install core openmas
    pip install openmas

    # Install support for gRPC
    pip install 'openmas[grpc]'

    # Install support for MCP (includes mcp-sdk)
    pip install 'openmas[mcp]'

    # Install support for MQTT
    pip install 'openmas[mqtt]'

    # Install multiple extras
    pip install 'openmas[grpc,mcp]'

    # Install all optional communicators and features
    pip install 'openmas[all]'
    ```
    (Use `poetry add 'openmas[extra]'` if using Poetry).

This approach keeps the core `openmas` package lightweight and ensures users only install what they need.

## Available Protocols & Communicators

### HTTP (`HttpCommunicator`)

* **Protocol:** Standard HTTP/1.1 (using `httpx`).
* **Best For:** RESTful API interactions, web service integration, general-purpose request/response communication between agents/services across processes or machines.
* **Dependencies:** `httpx` (likely a core dependency).
* **Configuration:** `communicator_type: http`. Options like `http_port` (server mode), `timeout`, `retries` can be set in `communicator_options`.

### Model Context Protocol (MCP)

MCP is designed for interacting with AI models and tools, particularly from Anthropic. OpenMAS provides two communicators for MCP. Requires `openmas[mcp]`.

1.  **`McpSseCommunicator`**
    * **Protocol:** MCP over HTTP Server-Sent Events (SSE).
    * **Best For:** Networked MCP communication. Running an agent as an HTTP-based MCP server (e.g., for a UI to connect to) or connecting to remote HTTP-based MCP services.
    * **Dependencies:** `mcp` SDK, `fastapi`, `uvicorn`, `httpx`.
    * **Configuration:** `communicator_type: mcp_sse`. Options: `server_mode` (bool), `http_port` (server mode).

2.  **`McpStdioCommunicator`**
    * **Protocol:** MCP over standard input/output.
    * **Best For:** Running an agent as an MCP service interacted with via stdin/stdout (e.g., as a CLI tool or managed subprocess). Connecting to external tools/engines that expose an MCP interface via stdio (like Stockfish configured for MCP).
    * **Dependencies:** `mcp` SDK.
    * **Configuration:** `communicator_type: mcp_stdio`. Options: `server_mode` (bool).

### gRPC (`GrpcCommunicator`)

* **Protocol:** gRPC (using `grpcio`).
* **Best For:** High-performance, low-latency RPC between services, potentially across different languages. Streaming scenarios. Microservice architectures where gRPC is standard. Requires `openmas[grpc]`.
* **Dependencies:** `grpcio`, `grpcio-tools`.
* **Configuration:** `communicator_type: grpc`. Options: `server_mode` (bool), `grpc_port` (server mode).
* **Note:** The default implementation uses a generic dictionary format. For type-safe communication using Protobuf definitions, customization might be needed.

### MQTT (`MqttCommunicator`)

* **Protocol:** MQTT (using `paho-mqtt`).
* **Best For:** Publish/subscribe messaging patterns, event-driven architectures, decoupled communication, IoT applications. Requires an external MQTT broker. Requires `openmas[mqtt]`.
* **Dependencies:** `paho-mqtt`.
* **Configuration:** `communicator_type: mqtt`. Options: `broker_host`, `broker_port`, `username`, `password`, `client_id`, TLS settings.

## Choosing the Right Protocol

| Scenario                                      | Recommended Communicator(s) | Why?                                                                 |
| :-------------------------------------------- | :------------------------ | :------------------------------------------------------------------- |
| General Request/Response between Agents/Services | `HttpCommunicator`        | Standard, widely supported, good for RESTful patterns.               |
| Interacting with Anthropic Models/MCP Services | `McpSseCommunicator`      | Native MCP support over standard web protocols.                      |
| Exposing Agent as HTTP-based MCP Server       | `McpSseCommunicator`      | Allows web clients/other services to interact via MCP over HTTP/SSE. |
| Agent as CLI Tool using MCP                 | `McpStdioCommunicator`    | Uses stdin/stdout for MCP interaction.                               |
| Connecting to MCP Tool via Subprocess (e.g. Stockfish) | `McpStdioCommunicator`    | Manages subprocess communication via MCP over stdio.                 |
| High-Performance RPC                          | `GrpcCommunicator`        | Efficient binary protocol, good for low-latency internal comms.      |
| Publish/Subscribe, Event-Driven Systems       | `MqttCommunicator`        | Decoupled messaging via a broker, suitable for event notifications.  |
| Agents in the Same Process (Testing/Simple) | `MockCommunicator` (testing) or potentially a future `InMemoryCommunicator` | Lowest latency, avoids network overhead.                             |

## Communicator Configuration Options

Refer to the specific communicator class documentation (or source code) and the [Configuration Guide](configuration.md) for detailed options applicable to each communicator type (e.g., `http_port`, `grpc_port`, `broker_host`, `server_mode`, `timeout`). These are typically set within the `communicator_options` dictionary in your configuration.

## MCP Method Mapping (Client Perspective)

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

**Note:** This mapping applies when your OpenMAS agent is acting as an *MCP client*. When your agent acts as an *MCP server* (using `MCPServerAgent` or a communicator in `server_mode=True`), incoming MCP requests trigger the methods decorated with `@mcp_tool`, `@mcp_prompt`, or `@mcp_resource` within your agent. See the [MCP Integration Guide](mcp_integration.md).

## Extending with Custom Protocols

OpenMAS allows you to create custom protocol implementations by extending the `BaseCommunicator` class and potentially leveraging the communicator extension system (see `communicator_extensions.md`).


# Communication in OpenMAS (OLD)

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
