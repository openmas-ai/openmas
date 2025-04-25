# OpenMAS Docstring Policy

This document defines the standard format for docstrings in the OpenMAS codebase.

## Docstring Style

OpenMAS uses **Google-style docstrings** throughout the codebase. This style is chosen for its readability, ease of use, and compatibility with tools like Sphinx and mkdocs.

## Required Elements

### Module Docstrings

Each Python module should have a docstring at the top that describes its purpose:

```python
"""OpenMAS communication module.

This module provides communication infrastructure for agents to exchange
messages using various protocols and message formats.
"""
```

### Class Docstrings

Each class should have a docstring describing its purpose, behavior, and usage:

```python
class Agent:
    """The main agent class for building multi-agent systems.

    Agent handles message routing, state management, and communication
    with other agents and services. It provides a simple interface for
    developers to focus on business logic.

    Attributes:
        name: The name of the agent.
        communicator: The communicator instance used by this agent.
    """
```

### Method and Function Docstrings

Each method and function should have a docstring describing its purpose, parameters, return values, and exceptions:

```python
async def send_request(
    self,
    target_service: str,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    response_model: Optional[Type[BaseModel]] = None,
    timeout: Optional[float] = None,
) -> Any:
    """Send a request to a target service and wait for a response.

    Args:
        target_service: The name of the target service.
        method: The method name to call on the target service.
        params: Optional parameters to pass to the method.
        response_model: Optional Pydantic model to validate and parse the response.
        timeout: Optional timeout in seconds. None means use default timeout.

    Returns:
        The parsed response from the target service. If response_model is provided,
        the response will be validated and parsed into that model.

    Raises:
        ServiceNotFoundError: If the target service is not found.
        CommunicationError: If there is a problem with communication.
        ValidationError: If response validation fails.
        TimeoutError: If the request times out.
    """
```

### Property Docstrings

Properties should also have docstrings:

```python
@property
def is_running(self) -> bool:
    """Return True if the agent is currently running."""
    return self._is_running
```

## Documentation Tools

The project uses Sphinx with the `napoleon` extension to generate documentation from Google-style docstrings. To build documentation, run:

```bash
poetry run sphinx-build -b html docs/source docs/build/html
```

## Style Guidelines

1. **Keep docstrings clear and concise**: Focus on conveying meaning, not just describing the code.
2. **Always document parameters and return values**: This helps users understand how to use functions.
3. **Document exceptions**: List all exceptions that can be raised and the conditions under which they occur.
4. **Use type hints**: Combine docstrings with Python type hints for better documentation.
5. **Document complex logic**: If a method contains complex logic, explain the reason and approach.
6. **Example usage**: For public APIs, consider including example usage.

```python
def get_logger(name: str) -> Logger:
    """Get a logger instance for the given name.

    Args:
        name: The name for the logger, typically __name__.

    Returns:
        A Logger instance configured with the OpenMAS logging settings.

    Example:
        ```python
        from openmas.logging import get_logger

        logger = get_logger(__name__)
        logger.info("This is a log message")
        ```
    """
```

## Validation

The CI pipeline includes a check for docstring coverage and compliance with this policy using the `pydocstyle` tool. Ensure all new code follows these guidelines to pass CI checks.
