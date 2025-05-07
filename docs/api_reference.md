# OpenMAS API Reference

This document provides a reference for the key classes and methods in the OpenMAS SDK.

## Agent Module

### BaseAgent

```python
from openmas.agent import BaseAgent

class MyAgent(BaseAgent):
    async def setup(self) -> None:
        """Set up the agent."""
        pass

    async def run(self) -> None:
        """Run the agent."""
        pass

    async def shutdown(self) -> None:
        """Shut down the agent."""
        pass
```

Key methods:
- `__init__(name=None, config=None, communicator_class=None, **kwargs)`: Initialize the agent
- `setup()`: Set up the agent (called by `start()`)
- `run()`: Run the agent (called by `start()`)
- `shutdown()`: Shut down the agent (called by `stop()`)
- `start()`: Start the agent (calls `setup()` then `run()`)
- `stop()`: Stop the agent (calls `shutdown()`)
- `set_communicator(communicator)`: Set the agent's communicator
- `get_handler(method)`: Get a handler for the specified method
- `register_handler(method, handler)`: Register a handler for the specified method

### MCP Agents

```python
from openmas.agent import McpAgent, McpServerAgent, McpClientAgent

# Base MCP agent
class MyMcpAgent(McpAgent):
    pass

# MCP server agent
class MyServerAgent(McpServerAgent):
    pass

# MCP client agent
class MyClientAgent(McpClientAgent):
    pass
```

#### McpAgent

Key methods inherited from BaseAgent, plus:
- `_discover_mcp_methods()`: Discover methods decorated with MCP decorators
- `register_with_server(server)`: Register the agent's MCP methods with an MCP server

#### McpServerAgent

Key methods:
- `setup_communicator()`: Set up the MCP communicator (SSE or stdio)
- `start_server()`: Start the MCP server
- `stop_server()`: Stop the MCP server

#### McpClientAgent

Key methods:
- `connect_to_service(service_name, host, port)`: Connect to an MCP service
- `disconnect_from_service(service_name)`: Disconnect from an MCP service
- `list_tools(service_name)`: List tools available on a service
- `call_tool(service_name, tool_name, params)`: Call a tool on a service

### MCP Decorators

<a id="openmas.prompt"></a>
```python
from openmas.agent import mcp_tool, mcp_prompt, mcp_resource

class MyAgent(McpAgent):
    @mcp_tool(name="my_tool", description="My tool")
    async def my_tool(self, param1: str) -> dict:
        """Tool documentation."""
        return {"result": param1}

    @mcp_prompt(name="my_prompt", description="My prompt")
    async def my_prompt(self, context: str) -> str:
        """Prompt documentation."""
        return f"Context: {context}\n\nResponse:"

    @mcp_resource(uri="/resource", name="my_resource", mime_type="application/json")
    async def my_resource(self) -> bytes:
        """Resource documentation."""
        return b'{"key": "value"}'
```

## Communication Module

### Base Communicator

```python
from openmas.communication import BaseCommunicator

# Abstract base class, not used directly
```

### HTTP Communicator

```python
from openmas.communication import HttpCommunicator

communicator = HttpCommunicator(
    agent_name="my-agent",
    service_urls={"other-service": "http://localhost:8000"},
    http_port=8001
)
```

Key methods:
- `start()`: Start the communicator
- `stop()`: Stop the communicator
- `register_handler(method, handler)`: Register a handler for the specified method
- `send_request(target_service, method, params)`: Send a request to a service
- `send_notification(target_service, method, params)`: Send a notification to a service

### MCP Communicators

```python
from openmas.communication.mcp import McpSseCommunicator, McpStdioCommunicator

# SSE-based MCP communicator (HTTP/SSE)
sse_communicator = McpSseCommunicator(
    agent_name="my-agent",
    service_urls={"mcp-service": "http://localhost:8000"},
    server_mode=False,
    http_port=8001
)

# Stdio-based MCP communicator (stdin/stdout)
stdio_communicator = McpStdioCommunicator(
    agent_name="my-agent",
    service_urls={},
    server_mode=True
)
```

Key methods (both communicators):
- `start()`: Start the communicator
- `stop()`: Stop the communicator
- `register_handler(method, handler)`: Register a handler for the specified method
- `register_mcp_methods(agent)`: Register the agent's MCP methods with the server

### gRPC Communicator

```python
from openmas.communication.grpc import GrpcCommunicator

grpc_communicator = GrpcCommunicator(
    agent_name="my-agent",
    service_urls={"grpc-service": "localhost:50051"},
    grpc_port=50052
)
```

### MQTT Communicator

```python
from openmas.communication.mqtt import MqttCommunicator

mqtt_communicator = MqttCommunicator(
    agent_name="my-agent",
    service_urls={},
    broker_host="localhost",
    broker_port=1883
)
```

## Configuration Module

```python
from openmas.config import load_config, AgentConfig
from pydantic import Field

# Load standard configuration
config = load_config(AgentConfig)

# Define custom configuration
class MyAgentConfig(AgentConfig):
    api_key: str = Field(..., description="API key for external service")
    model_name: str = Field("gpt-4", description="Model name to use")

# Load custom configuration
my_config = load_config(MyAgentConfig)
```

Key functions:
- `load_config(config_class)`: Load configuration from environment, files, etc.
- `find_project_root()`: Find the root directory of the OpenMAS project

### AgentConfig

Key fields:
- `name`: Agent name (default: "agent")
- `log_level`: Logging level (default: "INFO")
- `communicator_type`: Type of communicator (default: "http")
- `service_urls`: Dictionary of service URLs (default: {})
- `communicator_options`: Dictionary of options for the communicator (default: {})

## Testing Module

```python
import pytest
from openmas.testing import MockCommunicator, AgentTestHarness
from openmas.agent import BaseAgent

# Create a mock communicator
mock_communicator = MockCommunicator(agent_name="test-agent")

# Create a test harness
test_harness = AgentTestHarness(
    agent_class=BaseAgent,
    default_config={"name": "test-agent"}
)
```

### MockCommunicator

Key methods:
- `expect_request(target_service, method, params, response)`: Expect a request and return a response
- `expect_request_exception(target_service, method, params, exception)`: Expect a request and raise an exception
- `expect_notification(target_service, method, params)`: Expect a notification
- `verify()`: Verify that all expectations were met
- `trigger_handler(method, params)`: Trigger a handler for testing

### AgentTestHarness

Key methods:
- `create_agent(**kwargs)`: Create an agent instance
- `running_agent(agent)`: Context manager for running an agent during tests
- `running_agents(*agents)`: Context manager for running multiple agents
- `link_agents(*agents)`: Link agents for in-memory communication
- `trigger_handler(agent, method, params)`: Trigger a handler on an agent
- `wait_for(condition, timeout, check_interval)`: Wait for a condition to be true
- `verify_all_communicators()`: Verify all communicators' expectations

## Logging Module

```python
from openmas.logging import get_logger, configure_logging

# Configure logging
configure_logging(log_level="DEBUG")

# Get a logger
logger = get_logger(__name__)

# Use the logger
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

Key functions:
- `get_logger(name)`: Get a logger with the specified name
- `configure_logging(log_level, json_format)`: Configure logging for the application

## Agent Patterns

<a id="openmas.sampling"></a>
::: openmas.patterns.orchestrator
    options:
        show_source: yes
        members:
            - BaseOrchestratorAgent
            - BaseWorkerAgent
            - TaskHandler
            - TaskRequest
            - TaskResult
            - WorkerInfo

::: openmas.patterns.chaining
    options:
        show_source: yes
        members:
            - ServiceChain
            - ChainBuilder
            - create_chain
            - execute_chain

## Deployment

::: openmas.deployment.generators
    options:
      show_source: yes
      members:
        - generate_docker_compose
        - generate_kubernetes_manifests
        - generate_dockerfile
