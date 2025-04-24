# Basic SimpleMAS Examples

This directory contains basic examples that demonstrate the core functionality of the SimpleMAS framework. These examples are a good starting point for understanding the framework's architecture and capabilities.

## Examples

### Hello World Example

[hello_world.py](hello_world.py) - A minimal example showing two agents exchanging greeting messages. This example demonstrates:
- Basic agent creation and configuration
- Message handling and registration
- Agent lifecycle management
- Asynchronous agent operation

To run:
```bash
poetry run python examples/basic/hello_world.py
```

### Simple Agent Example

[simple_agent.py](simple_agent.py) - Demonstrates a standalone agent that performs periodic tasks. This example shows:
- Agent state management
- Implementing the agent lifecycle methods
- Periodic task execution
- Basic reporting

To run:
```bash
poetry run python examples/basic/simple_agent.py
```

### Minimal Agent Example

[minimal_agent.py](minimal_agent.py) - Shows the absolute minimum required for a functional agent with ping/pong communication. This example covers:
- Bare minimum agent implementation
- Basic message handling
- Request/response pattern
- Agent status reporting

To run:
```bash
poetry run python examples/basic/minimal_agent.py
```

## Testing the Examples

Each example has corresponding tests in the `tests/unit/examples/` directory that demonstrate how to test agent behavior using the SimpleMAS testing utilities.

To run the tests:
```bash
poetry run pytest tests/unit/examples/
```

## Extending the Examples

These examples provide a foundation that you can build upon for your own agents:

1. Start with hello_world.py to understand the basic structure
2. Implement your own message handlers based on your application's needs
3. Customize agent behavior by overriding the appropriate lifecycle methods
