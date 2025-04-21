# SimpleMas Communication Module

This module provides the communication infrastructure for the SimpleMas framework, enabling agents to exchange messages using various protocols.

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

Any new protocol implementation must adhere to this interface to ensure compatibility with the SimpleMas framework.

## Protocol Plugin System

The communication module is designed with a plugin architecture to allow easy addition of new protocol implementations:

1. Implement the `BaseCommunicator` interface
2. Register the implementation in the module's `__init__.py`
3. Document the protocol's characteristics, configuration, and use cases

This design allows for easy extension of SimpleMas with custom protocols tailored to specific deployment environments or performance requirements.

## Directory Structure

```
communication/
├── __init__.py          # Module initialization and protocol registration
├── base.py              # BaseCommunicator abstract base class
├── http.py              # HTTP protocol implementation
├── mcp/                 # Message Channel Protocol implementation
│   ├── __init__.py
│   ├── channel.py       # Channel implementation
│   └── communicator.py  # MCP communicator implementation
└── README.md            # This file
```

## Implemented Protocols

### HTTP Protocol

The HTTP protocol implementation (`http.py`) provides communication over HTTP, making it suitable for distributed agents running on different machines or in different processes. It uses JSON-RPC over HTTP for message formatting.

For details, see the [HTTP Protocol Documentation](../../docs/communication.md#http-communication).

### Message Channel Protocol (MCP)

The Message Channel Protocol implementation (`mcp/`) provides high-performance in-memory communication for agents running in the same process. It's optimized for low-latency, high-throughput communication.

For details, see the [MCP Documentation](../../docs/communication.md#message-channel-protocol-mcp).

## For Developers

When implementing a new protocol:

1. Create a new file or package for your protocol implementation
2. Extend `BaseCommunicator` and implement all required methods
3. Add appropriate error handling and logging
4. Write comprehensive tests for your implementation
5. Update the module's `__init__.py` to expose your implementation
6. Document your protocol in the user-facing documentation

See the existing protocol implementations for reference.
