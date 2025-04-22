# gRPC Communicator for SimpleMas

This module provides a gRPC-based communicator implementation for SimpleMas. It enables agents to communicate with each other using Google's [gRPC](https://grpc.io/) framework, offering high-performance, cross-language communication.

## Features

- **High Performance**: Efficient binary serialization using Protocol Buffers
- **Strong Typing**: Type-safe communication defined by proto files
- **Bidirectional**: Support for both client and server roles
- **Pluggable**: Integrates with SimpleMas's communicator plugin system

## Requirements

To use the gRPC communicator, you need to install the following packages:

```bash
pip install grpcio grpcio-tools protobuf
```

## Message Structure

The gRPC communicator uses a generic message structure defined in `simple_mas.proto`:

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
from simple_mas.agent import BaseAgent
from simple_mas.config import AgentConfig

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
from simple_mas.agent import BaseAgent
from simple_mas.config import AgentConfig

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
cd src/simple_mas/communication/grpc
python generate_proto.py
```

This will generate `simple_mas_pb2.py` and `simple_mas_pb2_grpc.py` which are used by the communicator.

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
4. Register your communicator with SimpleMas's plugin system

## Design Considerations

- **JSON Serialization**: Parameters and results are serialized as JSON strings to maintain compatibility with other communicators
- **Generic Service**: Uses a single generic service definition to handle all requests/notifications
- **Async Implementation**: Built on `grpc.aio` for async/await support
- **Error Handling**: Maps gRPC errors to SimpleMas exception types
