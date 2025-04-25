# OpenMAS API Reference

This document provides a reference to the core API of OpenMAS.

## Agent

### `Agent`

```python
class Agent:
    def __init__(
        self,
        name: str,
        communicator: BaseCommunicator,
        http_port: Optional[int] = None
    ): ...
```

The main agent class that coordinates communication and message handling.

**Parameters:**
- `name`: The name of the agent
- `communicator`: An instance of a class implementing `BaseCommunicator`
- `http_port`: Optional port for HTTP server when using HTTP communication

**Methods:**

```python
async def start() -> None: ...
```
Start the agent and its communicator.

```python
async def stop() -> None: ...
```
Stop the agent and its communicator.

```python
def handler(method: str) -> Callable: ...
```
Decorator to register a method handler.

```python
async def send_request(
    target_service: str,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    response_model: Optional[Type[BaseModel]] = None,
    timeout: Optional[float] = None
) -> Any: ...
```
Send a request to a target service and wait for a response.

```python
async def send_notification(
    target_service: str,
    method: str,
    params: Optional[Dict[str, Any]] = None
) -> None: ...
```
Send a one-way notification to a target service.

## Communication

### `BaseCommunicator`

```python
class BaseCommunicator(abc.ABC):
    def __init__(self, agent_name: str, service_urls: Dict[str, str]): ...
```

Abstract base class for all communicators.

**Parameters:**
- `agent_name`: The name of the agent using this communicator
- `service_urls`: Mapping of service names to URLs

**Methods:**

```python
@abc.abstractmethod
async def send_request(
    self,
    target_service: str,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    response_model: Optional[Type[T]] = None,
    timeout: Optional[float] = None,
) -> Any: ...
```
Send a request to a target service.

```python
@abc.abstractmethod
async def send_notification(
    self, target_service: str, method: str, params: Optional[Dict[str, Any]] = None
) -> None: ...
```
Send a notification to a target service.

```python
@abc.abstractmethod
async def register_handler(self, method: str, handler: Callable) -> None: ...
```
Register a handler for a method.

```python
@abc.abstractmethod
async def start(self) -> None: ...
```
Start the communicator.

```python
@abc.abstractmethod
async def stop(self) -> None: ...
```
Stop the communicator.

### `HTTPCommunicator`

```python
class HTTPCommunicator(BaseCommunicator):
    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        http_port: Optional[int] = None,
        session: Optional[aiohttp.ClientSession] = None
    ): ...
```

HTTP-based communicator implementation.

### `MCPCommunicator`

```python
class MCPCommunicator(BaseCommunicator):
    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str]
    ): ...
```

Message Channel Protocol communicator for high-performance in-memory communication.

## Logging

```python
def get_logger(name: str) -> Logger: ...
```

Get a logger instance for the given name.

**Example:**
```python
from openmas.logging import get_logger

logger = get_logger(__name__)
logger.info("Message", key="value")
```

## Exceptions

```python
class ServiceNotFoundError(Exception): ...
```
Raised when a target service is not found.

```python
class CommunicationError(Exception): ...
```
Base class for communication-related errors.

```python
class TimeoutError(CommunicationError): ...
```
Raised when a request times out.

```python
class ValidationError(Exception): ...
```
Raised when response validation fails.
