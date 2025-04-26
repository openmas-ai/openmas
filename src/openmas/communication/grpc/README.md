# gRPC Communicator for OpenMAS

This module provides a gRPC-based communicator implementation for OpenMAS. It enables agents to communicate with each other using Google's [gRPC](https://grpc.io/) framework, offering high-performance, cross-language communication.

## Features

- **High Performance**: Efficient binary serialization using Protocol Buffers
- **Strong Typing**: Type-safe communication defined by proto files
- **Bidirectional**: Support for both client and server roles
- **Pluggable**: Integrates with OpenMAS's communicator extension system

## Requirements

To use the gRPC communicator, you need to install the following packages:

```bash
pip install grpcio grpcio-tools protobuf
```

## Message Structure

The gRPC communicator uses a generic message structure defined in `openmas.proto`:

1. **RequestMessage**: For sending requests from a client to a server
   - `id`: Unique identifier for the request
   - `source`: Name of the source agent
   - `target`: Name of the target service
   - `method`: Method to call on the service
   - `params`: JSON-encoded parameters
   - `timestamp`: Timestamp of the request
   - `timeout_ms`: Optional timeout in milliseconds

2. **ResponseMessage**: For sending responses from a server to a client
   - `id`: ID of the original request
   - `source`: Name of the source service
   - `target`: Name of the target agent
   - `result`: Binary response data (can be JSON or other format)
   - `error`: Optional error information
   - `timestamp`: Timestamp of the response

3. **NotificationMessage**: For sending one-way notifications
   - `source`: Name of the source agent
   - `target`: Name of the target service
   - `method`: Method to call on the service
   - `params`: JSON-encoded parameters
   - `timestamp`: Timestamp of the notification

## Usage

### Server Mode

To create an agent that runs a gRPC server:

```python
from openmas.agent import BaseAgent
from openmas.config import AgentConfig

agent = BaseAgent(
    config=AgentConfig(
        name="my_server_agent",
        communicator_type="grpc",
        communicator_options={
            "server_mode": True,
            "server_address": "localhost:50051",
            "max_workers": 10
        },
        service_urls={} # Not used in server mode
    )
)

# Register handlers for methods
await agent.communicator.register_handler("my_method", my_handler_function)
await agent.start()
```

### Client Mode

To create an agent that connects to gRPC servers:

```python
from openmas.agent import BaseAgent
from openmas.config import AgentConfig

agent = BaseAgent(
    config=AgentConfig(
        name="my_client_agent",
        communicator_type="grpc",
        service_urls={
            "server": "localhost:50051"
        }
    )
)

await agent.start()

# Send a request
response = await agent.communicator.send_request(
    target_service="server",
    method="my_method",
    params={"param1": "value1"},
    timeout=5.0
)

# Send a notification
await agent.communicator.send_notification(
    target_service="server",
    method="notify",
    params={"message": "This is a notification"}
)
```

## Error Handling and Status Mapping

The GrpcCommunicator maps between gRPC status codes and OpenMAS exception types:

| gRPC Status Code | Error Type | OpenMAS Exception |
|------------------|------------|---------------------|
| 404 | Method not found | `MethodNotFoundError` |
| 408 | Request timeout | `RequestTimeoutError` |
| Other error codes | Various errors | `CommunicationError` |

When a gRPC exception occurs (like `grpc.RpcError`), it's also wrapped in a `CommunicationError` with relevant details preserved.

AsyncIO timeouts (`asyncio.TimeoutError`) are mapped to `RequestTimeoutError`.

### Server-side Error Handling

When implementing handlers on the server side, exceptions are automatically caught and converted to appropriate error responses:

```python
async def my_handler(param1, param2):
    # If this raises an exception, it will be returned as an error
    # with code 500 and details including the exception type
    raise ValueError("Invalid parameter")
```

The client will receive a `CommunicationError` with the error message and details.

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `server_mode` | `False` | Whether to run in server mode |
| `server_address` | `[::]:50051` | Address to bind the server to (server mode only) |
| `max_workers` | `10` | Maximum number of server worker threads |
| `channel_options` | `{}` | Additional gRPC channel options |

## Protocol Generation

The module includes a script to generate Python code from the `.proto` file:

```bash
cd src/openmas/communication/grpc
python generate_proto.py
```

This will generate `openmas_pb2.py` and `openmas_pb2_grpc.py` which are used by the communicator.

## Testing the gRPC Communicator

When testing the GrpcCommunicator, you can use Python's unittest mock framework to avoid creating actual gRPC connections:

```python
import pytest
from unittest import mock
from openmas.communication.grpc import GrpcCommunicator

@pytest.fixture
def mock_grpc_channel():
    with mock.patch("grpc.aio.insecure_channel") as mock_channel_func:
        mock_channel = mock.AsyncMock()
        mock_channel_func.return_value = mock_channel
        yield mock_channel

@pytest.mark.asyncio
async def test_grpc_communicator(mock_grpc_channel):
    # Create a communicator
    communicator = GrpcCommunicator("test-agent", {"service": "localhost:50051"})

    # Mock the stub and its methods
    mock_stub = mock.AsyncMock()
    communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

    # Test sending a request
    await communicator.send_request("service", "method", {"param": "value"})

    # Verify the stub was called correctly
    mock_stub.SendRequest.assert_called_once()
```

For server testing, you can mock the gRPC server and verify handler registration:

```python
@pytest.fixture
def mock_grpc_server():
    with mock.patch("grpc.aio.server") as mock_server_func:
        mock_server = mock.AsyncMock()
        mock_server_func.return_value = mock_server
        yield mock_server

@pytest.mark.asyncio
async def test_server_mode(mock_grpc_server):
    communicator = GrpcCommunicator(
        "test-agent", {}, server_mode=True, server_address="localhost:50051"
    )

    await communicator.start()
    mock_grpc_server.return_value.add_insecure_port.assert_called_with("localhost:50051")
    mock_grpc_server.return_value.start.assert_called_once()
```

## Advanced Usage

### Custom Channel Options

You can configure advanced gRPC channel options:

```python
agent = BaseAgent(
    config=AgentConfig(
        name="my_agent",
        communicator_type="grpc",
        communicator_options={
            "channel_options": {
                "grpc.max_send_message_length": 16 * 1024 * 1024,  # 16 MB
                "grpc.max_receive_message_length": 16 * 1024 * 1024,  # 16 MB
                "grpc.keepalive_time_ms": 30000,  # 30 seconds
            }
        },
        service_urls={"server": "localhost:50051"}
    )
)
```

### Extending with Custom Service Definitions

While the default implementation uses a generic message structure, you can extend the gRPC communicator to use custom service definitions:

1. Create your own `.proto` file with specific service and message definitions
2. Generate the Python code using `protoc`
3. Implement a custom communicator class that extends `GrpcCommunicator`
4. Register your communicator with OpenMAS's extension system

## Design Considerations

- **JSON Serialization**: Parameters and results are serialized as JSON strings to maintain compatibility with other communicators
- **Generic Service**: Uses a single generic service definition to handle all requests/notifications
- **Async Implementation**: Built on `grpc.aio` for async/await support
- **Error Handling**: Maps gRPC errors to OpenMAS exception types
