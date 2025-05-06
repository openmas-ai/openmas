# How to Implement MCP 1.7.1 SSE Integration in OpenMAS

## Background and Problem Statement

OpenMAS currently has partial integration with the Model Context Protocol (MCP) 1.6, which has known issues and limitations. The goal is to upgrade to MCP 1.7.1, which provides a more stable API and better SSE (Server-Sent Events) support.

**Current Issues:**
1. The existing MCP SSE implementation is based on MCP 1.6, which has unstable behavior
2. Arguments are not properly passed between the client and server
3. Tool registration and handling don't align with MCP 1.7.1's expectations
4. Error handling is incomplete
5. Test coverage is insufficient, especially for edge cases
6. Documentation is outdated and doesn't cover known workarounds

**Goals:**
1. Create a clean MCP 1.7.1 implementation to replace the existing one, maintaining the same API
2. Ensure proper tool argument passing between client and server
3. Implement robust error handling
4. Update examples and documentation to reflect the improved implementation
5. Provide comprehensive integration tests with at least 80% coverage
6. Follow Test-Driven Development (TDD) methodology throughout the implementation
7. Abstract all MCP implementation complexities away from end users

## Important Implementation Principles

### Clean Implementation Approach

As OpenMAS is a new, unpublished library implementation, we have the opportunity to replace the existing implementation with a better one without concerns about backward compatibility:

- Replace the current MCP SSE implementation with a clean 1.7.1-based version
- Maintain the same communicator type name ("mcp-sse") for consistency
- Preserve the public API while improving the internal implementation
- Refactor and rewrite components as needed
- Optimize for current best practices and clean code
- Ruthlessly eliminate any unnecessary complexity

### Shielding End Users from MCP Complexities

A primary goal of this implementation is to absorb all the complexities and workarounds required for MCP 1.7.1 within the OpenMAS library itself, keeping them invisible to end users:

1. **Transparent Handling**: End users should be able to use standard patterns without knowing about the internal workarounds
2. **Clean API Surface**: The public API should be intuitive and hide implementation details
3. **Self-Healing**: The library should automatically detect and handle edge cases
4. **Sensible Defaults**: Provide defaults that work in most scenarios without configuration
5. **Comprehensive Documentation**: Document the library's behavior, not the workarounds

### Thorough Testing to Identify All Edge Cases

Before finalizing the implementation, extensive testing must be performed to identify and address all real-world nuances of MCP 1.7.1:

1. **Exhaustive Testing**: Test with different payload sizes, formats, and edge cases
2. **Protocol Exploration**: Test boundary conditions of the MCP 1.7.1 protocol
3. **Error Recovery**: Test how the system behaves under various error conditions
4. **Real-World Scenarios**: Test with realistic workflows and agent interactions
5. **Performance Testing**: Test under load to identify potential bottlenecks
6. **Cross-Environment Testing**: Test in different network conditions and environments

## Test-Driven Development Approach

All features must be implemented following TDD principles. For each component:

1. **Write the tests first**:
   - Start with unit tests for each new method or class
   - Write integration tests for end-to-end functionality
   - Include both success and failure scenarios

2. **Run the tests to confirm they fail**:
   - Verify that tests fail for the expected reasons
   - This confirms that the tests are valid and testing the right things

3. **Implement the minimum code to make tests pass**:
   - Focus on making the tests pass first
   - Avoid over-engineering or implementing features not covered by tests

4. **Refactor and optimize**:
   - Clean up the implementation while keeping tests passing
   - Optimize for readability and maintainability

5. **Repeat for each feature**:
   - Apply this cycle for each component of the MCP integration

### Coverage Requirements

All MCP-related features must have at least 80% test coverage:

1. **Unit tests**: Cover all methods and classes with unit tests
   - Focus on edge cases and error handling
   - Test different argument formats and response types
   - Mock external dependencies

2. **Integration tests**: Create end-to-end tests for real-world use cases
   - Test tool registration and calling
   - Test error handling and timeouts
   - Test with real network communication

3. **Coverage measurement**:
   - Use `pytest-cov` to measure coverage
   - Run coverage tests with: `poetry run pytest --cov=openmas.communication.mcp tests/ --cov-report=xml --cov-report=term`
   - CI pipeline should fail if coverage drops below 80%

## Implementation Plan

### 1. Update Dependencies

Update the `pyproject.toml` to specify MCP 1.7.1+ as the required version:

```toml
[tool.poetry.dependencies]
# Other dependencies
mcp = ">=1.7.1"
```

### 2. Write Tests for the Updated SSE Communicator

Before implementing the communicator, write comprehensive tests:

1. **Unit tests**: `tests/unit/communication/mcp/test_sse_communicator.py`
   - Test client-side methods (_get_service_url, send_request, call_tool)
   - Test server-side methods (register_tool, start, stop)
   - Test error handling and edge cases

2. **Mock integration tests**: `tests/integration/mcp/mock/test_openmas_mcp_sse.py`
   - Test client-server interaction with mocked network
   - Test tool registration and calling
   - Test error handling

3. **Real integration tests**: `tests/integration/mcp/real/test_openmas_mcp_sse.py`
   - Test with real network communication
   - Test end-to-end functionality
   - Test with actual MCP client and server

4. **Advanced edge case tests**: `tests/integration/mcp/real/test_openmas_mcp_edge_cases.py`
   - Test with malformed inputs
   - Test with large payloads
   - Test with concurrent tool calls
   - Test connection interruptions and recovery
   - Test with different content types

### 3. Update the SSE Communicator for MCP 1.7.1

Update the existing communicator file: `src/openmas/communication/mcp/sse_communicator.py`

This updated class should:
- Support both client and server modes
- Properly handle tool registration and calling
- Implement robust error handling
- Correctly format arguments and responses
- Abstract away all MCP 1.7.1 complexities from end users

The updated implementation should follow this structure:

```python
"""MCP Communicator using SSE for communication with MCP SDK 1.7.1+."""

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, cast

import structlog

# Conditionally import server-side FastMCP components
try:
    from mcp.server.fastmcp import FastMCP, Context
    from fastapi.responses import JSONResponse
    import mcp.types as mcp_types

    HAS_SERVER_DEPS = True
except ImportError:
    HAS_SERVER_DEPS = False
    FastMCP = None  # type: ignore
    JSONResponse = None  # type: ignore
    Context = None  # type: ignore
    mcp_types = None  # type: ignore

# Import client-side components
from mcp.client import sse
from mcp.client.session import ClientSession

# Import MCP types
try:
    from mcp.types import TextContent, CallToolResult

    HAS_MCP_TYPES = True
except ImportError:
    HAS_MCP_TYPES = False
    TextContent = Any  # type: ignore
    CallToolResult = Any  # type: ignore

from openmas.communication.base import BaseCommunicator, register_communicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError

# Set up logging
logger = structlog.get_logger(__name__)

# Type variable for generic return types
T = TypeVar("T")


class McpSseCommunicator(BaseCommunicator):
    """Communicator that uses MCP protocol over HTTP with Server-Sent Events for MCP SDK 1.7.1+.

    Handles both client and server modes using the modern FastMCP API.

    This implementation focuses on providing a clean, intuitive API that shields users from
    the underlying complexities of the MCP 1.7.1 protocol. All workarounds and edge case
    handling are implemented internally to provide a seamless experience for end users.
    """

    def __init__(
        self,
        agent_name: str,
        service_urls: Dict[str, str],
        server_mode: bool = False,
        http_port: int = 8000,
        http_host: str = "0.0.0.0",
        server_instructions: Optional[str] = None,
    ) -> None:
        """Initialize the MCP SSE communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to SSE endpoint URLs
            server_mode: Whether to run as a server
            http_port: Port to use when in server mode
            http_host: Host to bind to when in server mode
            server_instructions: Optional instructions for the server
        """
        super().__init__(agent_name, service_urls)
        self.server_mode = server_mode
        self.http_port = http_port
        self.http_host = http_host
        self.server_instructions = server_instructions or f"Agent: {agent_name}"

        # Server components (only used if server_mode is True)
        self.fastmcp_server: Optional[Any] = None
        self._server_task: Optional[asyncio.Task] = None
        self._background_tasks: Set[asyncio.Task] = set()

        # Initialize tool registry and handlers for server mode
        self.tool_registry: Dict[str, Dict[str, Any]] = {}
        self.handlers: Dict[str, Callable] = {}

        # Logger for this communicator
        self.logger = structlog.get_logger(__name__)

        if self.server_mode and not HAS_SERVER_DEPS:
            raise ImportError("MCP server dependencies (mcp[server]) are required for server mode.")

    # ... implement all methods for client and server modes
```

#### 3.1 Implement Client-side Methods

Focus on proper implementation of the following client methods:

- `_get_service_url`: Format URLs correctly for MCP 1.7.1
- `send_request`: Handle session initialization and tool calls
- `call_tool`: Format tool arguments correctly
- `list_tools`: List available tools on a service

Key implementation details for `call_tool`:

```python
async def call_tool(
    self,
    target_service: str,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Any:
    """Call an MCP tool on a target service.

    Args:
        target_service: Name of the service to call
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool
        timeout: Timeout in seconds

    Returns:
        The tool result
    """
    arguments = arguments or {}

    # Handle all MCP 1.7.1 argument formatting nuances internally
    # This shields users from having to know about the correct format
    formatted_arguments = self._format_arguments_for_mcp(arguments)

    method = f"tool/call/{tool_name}"
    return await self.send_request(target_service, method, formatted_arguments, timeout=timeout)

def _format_arguments_for_mcp(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Format arguments for MCP 1.7.1 compatibility.

    This internal method handles all the complexities of MCP 1.7.1 argument formatting,
    allowing the public API to remain clean and simple.

    Args:
        arguments: Original arguments from user

    Returns:
        Properly formatted arguments for MCP 1.7.1
    """
    # Create a copy to avoid modifying the original
    formatted_arguments = {**arguments}

    # Make sure we have a content field if text is present
    if "text" in arguments and "content" not in arguments:
        formatted_arguments["content"] = [
            {"type": "text", "text": arguments["text"]}
        ]

    # Handle other edge cases based on testing findings
    # ... additional formatting logic as needed ...

    return formatted_arguments
```

#### 3.2 Implement Server-side Methods

Focus on correct implementation of these server methods:

- `register_tool`: Register tools with proper handling of arguments
- `start`: Start the FastMCP server
- `stop`: Stop the server gracefully

The crucial part is tool registration and handling:

```python
def _register_tool_now(self, name: str, description: str, function: Callable) -> None:
    """Register a tool with the FastMCP server immediately."""
    if self.fastmcp_server is not None and HAS_SERVER_DEPS:
        logger.info(f"Adding tool '{name}' to running FastMCP server")

        # Create a properly formatted adapter for MCP 1.7.1 that handles all edge cases
        async def tool_adapter(ctx: Context) -> List[mcp_types.TextContent]:
            """Adapter function for MCP 1.7.1 tool calls.

            This adapter handles all the complexities of extracting arguments from the MCP context,
            allowing tool developers to focus on their business logic without worrying about
            MCP protocol details.
            """
            # Extract arguments using the internal helper that handles all edge cases
            arguments = self._extract_arguments_from_mcp_context(ctx)

            try:
                # Call the original handler function with clean arguments
                result = await function(arguments)

                # Format the result using an internal helper
                return self._format_result_for_mcp(result)
            except Exception as e:
                logger.error(f"Error in tool '{name}' handler: {e}")
                # Return error message as text
                return [mcp_types.TextContent(type="text", text=f"Error: {str(e)}")]

        # Register the tool with FastMCP using the correct API for 1.7.1
        self.fastmcp_server.add_tool(
            name=name,
            description=description,
            fn=tool_adapter,
        )
        logger.info(f"Tool '{name}' added to FastMCP server")
    else:
        logger.warning(f"Cannot add tool '{name}' - FastMCP server not created yet")

def _extract_arguments_from_mcp_context(self, ctx: Context) -> Dict[str, Any]:
    """Extract arguments from MCP 1.7.1 context, handling all edge cases.

    This internal method encapsulates all the logic needed to reliably extract
    arguments from the MCP context, regardless of how they were passed.

    Args:
        ctx: The MCP context object

    Returns:
        Extracted and normalized arguments
    """
    arguments = {}

    # Try to get arguments using different methods specific to MCP 1.7.1
    if hasattr(ctx, "request") and ctx.request is not None:
        # Try to get from request.params.arguments
        if hasattr(ctx.request, "params") and hasattr(ctx.request.params, "arguments"):
            arguments = ctx.request.params.arguments
        # Try to get from JSON body
        elif hasattr(ctx.request, "json_body") and isinstance(ctx.request.json_body, dict):
            json_body = ctx.request.json_body
            if "params" in json_body and isinstance(json_body["params"], dict):
                if "arguments" in json_body["params"]:
                    arguments = json_body["params"]["arguments"]

    # Use ctx.arguments as fallback
    if not arguments and hasattr(ctx, "arguments") and ctx.arguments:
        arguments = ctx.arguments

    # Handle special case for content field
    if "content" in arguments and isinstance(arguments["content"], list) and len(arguments["content"]) > 0:
        content_item = arguments["content"][0]
        if isinstance(content_item, dict) and "text" in content_item:
            # Extract text from content
            if "text" not in arguments:
                arguments["text"] = content_item["text"]

    return arguments

def _format_result_for_mcp(self, result: Any) -> List[mcp_types.TextContent]:
    """Format a result for MCP 1.7.1 compatibility.

    This internal method handles all the complexities of properly formatting
    results for MCP 1.7.1.

    Args:
        result: The original result from the handler

    Returns:
        Properly formatted MCP 1.7.1 TextContent list
    """
    if result is None:
        return []
    elif isinstance(result, (dict, list)):
        # Convert dictionary to JSON string
        result_json = json.dumps(result)
        return [mcp_types.TextContent(type="text", text=result_json)]
    elif isinstance(result, str):
        # Return string directly
        return [mcp_types.TextContent(type="text", text=result)]
    else:
        # Convert anything else to string
        return [mcp_types.TextContent(type="text", text=str(result))]
```

### 4. Update Example Agents

Update the existing examples to use the improved MCP 1.7.1 implementation:

1. **Update Tool Provider Agent**:
   - Use the improved McpSseCommunicator with MCP 1.7.1
   - Keep the interface simple, relying on the library to handle MCP complexities
   - Focus on business logic rather than protocol details

```python
async def process_text_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process text by converting to uppercase and counting words.

    Args:
        payload: Dictionary containing the text to process

    Returns:
        Dictionary containing the processed result
    """
    logger.info(f"Process text handler received payload: {payload}")

    # Notice how simple this implementation is - the communicator should handle
    # all the complexities of MCP 1.7.1 argument extraction
    if "text" not in payload:
        return {"error": "No text field found in payload", "status": "error"}

    text = payload["text"]

    # Process the text
    if not text:
        result = {"error": "Empty text input", "status": "error"}
    else:
        processed_text = text.upper()
        word_count = len(text.split())
        result = {"processed_text": processed_text, "word_count": word_count, "status": "success"}

    logger.info(f"Process text handler returning result: {result}")
    return result
```

2. **Update Tool User Agent**:
   - Use the improved McpSseCommunicator with MCP 1.7.1
   - Keep the interface simple and clean
   - Focus on business logic

```python
async def call_process_text(self, text: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Call the process_text tool on the tool provider.

    Args:
        text: The text to process
        timeout: Timeout in seconds

    Returns:
        The tool result

    Raises:
        CommunicationError: If the tool call fails
        asyncio.TimeoutError: If the tool call times out
    """
    logger.info(f"Calling process_text tool with text: {text}")

    try:
        # Notice the simplicity of the call - users shouldn't need to know about
        # the internal formatting requirements of MCP 1.7.1
        result = await asyncio.wait_for(
            self.communicator.call_tool(
                target_service="tool_provider",
                tool_name="process_text",
                arguments={"text": text},
            ),
            timeout=timeout,
        )

        logger.info(f"Received tool result: {result}")
        return result

    except asyncio.TimeoutError:
        error_msg = f"Tool call timed out after {timeout} seconds"
        logger.error(error_msg)
        raise
    except Exception as e:
        error_msg = f"Error calling tool: {e}"
        logger.error(error_msg)
        raise CommunicationError(f"Failed to call process_text: {e}")
```

### 5. Update Example Configuration

Update the example configuration file to use the improved implementation:

```yaml
name: example_08_mcp_sse
version: 0.1.0
description: "Example demonstrating MCP tool calls over Server-Sent Events (SSE) using MCP SDK 1.7.1"

# Define the available agents
agents:
  tool_provider: "agents/tool_provider"
  tool_user: "agents/tool_user"

# Default configuration for all agents
default_config:
  log_level: INFO

# Default communicator settings
communicator_defaults:
  type: mock
  options:
    server_mode: false

# Agent-specific configurations
agent_configs:
  # Tool provider config - use mcp-sse in server mode to expose MCP tools via HTTP/SSE
  tool_provider:
    communicator_type: mcp-sse
    communicator_options:
      server_mode: true
      http_port: 8080
      server_instructions: "A service that processes text using MCP tools over SSE"

  # Tool user config - use mcp-sse in client mode
  tool_user:
    communicator_type: mcp-sse
    communicator_options:
      server_mode: false
    service_urls:
      # The tool provider exposes an MCP SSE endpoint at /sse
      tool_provider: "http://localhost:8080/sse"

# Dependencies configuration (for external packages)
dependencies:
  - package: "mcp"
    version: ">=1.7.1"
```

### 6. Real-World Testing with Advanced Scenarios

To ensure the implementation handles all real-world complexities of MCP 1.7.1, create a dedicated testing phase:

1. **Create a comprehensive test matrix**:
   - Different payload types and sizes
   - Network interruptions and reconnections
   - Concurrent tool calls
   - Tool calls with timeouts
   - Tool calls with errors
   - Different argument formats
   - Different response formats

2. **Implement test harness**:
   - Create a test server with multiple tools
   - Create a test client that calls these tools
   - Add metrics collection for performance analysis
   - Add logging for detailed analysis

3. **Run tests in different environments**:
   - Local development
   - CI pipeline
   - Different operating systems
   - Different network conditions (using network shaping)

4. **Analyze and document findings**:
   - Document all observed behaviors
   - Identify edge cases and quirks
   - Implement workarounds in the library
   - Add automated tests for all edge cases

5. **Update library implementation**:
   - Refine the internal handling based on findings
   - Improve robustness and error handling
   - Ensure all complexities are hidden from end users

### 7. Comprehensive Documentation Updates

#### 7.1 Update Module Documentation

Add docstrings to all updated components with examples of usage. Each class and method should have:

- Clear description of what it does
- Parameters and return types documented
- Examples of usage
- Clean, simple examples that don't expose MCP complexities

#### 7.2 Update Example Documentation

Update the example documentation:

Include:
- Overview of MCP SSE integration
- Step-by-step guide on how to run the example
- Detailed explanation of each component
- Expected behavior and output
- Focus on the simplicity of using the API, not on workarounds
- Troubleshooting guide that addresses common issues

#### 7.3 Update Main Documentation

Update the main OpenMAS documentation to reflect the improved MCP integration:

1. Update `docs/guides/mcp_integration.md` with:
   - Improved MCP 1.7.1 integration details
   - Best practices for working with MCP
   - Clear examples of proper usage
   - Focus on the clean API rather than underlying complexities

2. Update `docs/guides/mcp_sse_tool_call_tutorial.md` with:
   - Updated tutorial for MCP 1.7.1
   - Simple, clean examples
   - Debugging guide

3. Update API reference documentation for:
   - `McpSseCommunicator` class
   - Tool registration and calling
   - Error handling
   - Focus on the public API, not internal implementation details

## Leveraging Existing Spike Branch Implementation

A significant amount of work has already been done on the spike branch to integrate OpenMAS with MCP 1.7.1. Rather than starting from scratch, the implementation should build upon this existing work while ensuring a clean, unified API design.

### Key Files to Review

The following files from the spike branch contain valuable implementations and tests that should be reviewed and leveraged:

1. **Communicator Implementation**:
   - `src/openmas/communication/mcp/sse_communicator_1_7_1.py` - Contains a working implementation of MCP 1.7.1 integration

2. **Unit Tests**:
   - `tests/unit/communication/mcp/test_sse_communicator_1_7_1.py` - Comprehensive unit tests for the MCP 1.7.1 communicator
   - `tests/unit/communication/test_mcp_communicator_registration.py` - Tests for communicator registration

3. **Integration Tests**:
   - `tests/integration/mcp/mock/test_mcp_1_7_1_sse.py` - Mock integration tests for the MCP 1.7.1 communicator
   - `tests/integration/mcp/real/test_openmas_mcp_1_7_1_sse.py` - Real integration tests with actual network communication
   - `tests/integration/mcp/real/test_mcp_1_7_1_edge_cases.py` - Tests targeting specific edge cases

4. **Registry Integration**:
   - `src/openmas/communication/__init__.py` - Contains changes for registering the MCP 1.7.1 communicator

### How to Leverage This Existing Work

1. **Study the Implementation Pattern**:
   - Analyze the existing implementation to understand how it handles MCP 1.7.1 intricacies
   - Note the successful patterns for argument formatting, extraction, and result handling
   - Identify edge cases that have already been solved

2. **Review Test Coverage**:
   - Study the test suite to understand what edge cases have been identified
   - Use these tests as a blueprint for ensuring comprehensive coverage
   - Pay special attention to the edge case tests that reveal protocol nuances

3. **Adapt the Code for the Final Implementation**:
   - Port the successful elements from the spike branch to update the main `McpSseCommunicator` class
   - Maintain the robust error handling and edge case management
   - Keep the clean API design while incorporating the internal complexity handling

4. **Consolidate Test Patterns**:
   - Adapt the test suite to work with the updated main communicator
   - Preserve the testing patterns that successfully catch edge cases
   - Ensure similar test coverage for the updated implementation

5. **Document Learnings**:
   - Document any important insights from the spike implementation
   - Note patterns that are especially effective at handling MCP 1.7.1 quirks
   - Share these insights with other developers

### Implementation Approach

1. Start by thoroughly reviewing the spike branch code to understand its approach
2. Identify the core patterns and solutions that successfully address MCP 1.7.1 challenges
3. Apply these patterns to update the main `McpSseCommunicator` implementation
4. Adapt and port the tests to verify the updated implementation
5. Preserve the innovative solutions while ensuring a clean, consistent API

This approach allows us to benefit from the valuable work already done while maintaining the goal of a single, unified, and clean implementation that provides the best user experience.

## Implementation Notes and Best Practices

### UX-Focused Design: Shielding Users from MCP Complexities

The primary goal of this implementation is to provide a clean, intuitive API that shields users from the complexities of the MCP 1.7.1 protocol:

1. **All workarounds should be internal**: Users should never need to implement workarounds in their code
2. **Sensible defaults**: Provide defaults that work in most scenarios
3. **Transparent handling**: Handle edge cases transparently without user intervention
4. **Clear error messages**: Provide helpful error messages that guide users toward solutions
5. **Robust recovery**: Implement automatic reconnection and recovery mechanisms

### Handling Tool Arguments

The primary challenge in MCP 1.7.1 integration is properly handling tool arguments. All these complexities should be handled internally by the library:

1. **Client-side**: The library should automatically format arguments correctly:
   ```python
   # User provides simple arguments:
   arguments={"text": "Hello world"}

   # Library internally formats for MCP 1.7.1:
   formatted_arguments = {
       "text": "Hello world",
       "content": [{"type": "text", "text": "Hello world"}]
   }
   ```

2. **Server-side**: The library should handle all extraction logic:
   ```python
   # Library extracts arguments from various locations
   arguments = self._extract_arguments_from_mcp_context(ctx)

   # User receives clean arguments:
   {"text": "Hello world"}
   ```

### Advanced Testing for Edge Cases

To ensure all MCP 1.7.1 complexities are handled correctly, implement a comprehensive testing strategy:

1. **Test matrix**: Create a comprehensive test matrix covering all edge cases
2. **Stress testing**: Test the system under high load to identify race conditions
3. **Error injection**: Deliberately inject errors to test recovery
4. **Protocol exploration**: Experiment with different MCP message formats
5. **Long-running tests**: Test the system over extended periods
6. **Cross-environment testing**: Test on different operating systems and Python versions
7. **Network condition simulation**: Test under various network conditions (latency, packet loss)

### Known Issues and Internal Workarounds

Document all known issues for internal reference, but implement workarounds transparently:

1. **Empty Arguments Issue**: The server-side handler may receive empty arguments even when the client sends them properly.
   - **Internal Workaround**: Implement argument extraction from multiple locations in the context

2. **Context Object Structure**: The Context object structure in MCP 1.7.1 differs from 1.6.
   - **Internal Workaround**: Use reflection to safely check for and access attributes

3. **Tool Registration Timing**: Tools must be registered after the server is started.
   - **Internal Workaround**: Queue tool registrations and apply them when the server is ready

4. **Content Format Differences**: The content format in MCP 1.7.1 differs from 1.6.
   - **Internal Workaround**: Support multiple formats internally but present a unified view to users

All these workarounds should be implemented within the library and thoroughly tested to ensure they handle all real-world scenarios properly.

### Error Handling

Implement comprehensive error handling internally:

1. Catch and properly log all exceptions
2. Return structured error responses
3. Add timeouts to all network operations
4. Handle server startup/shutdown gracefully
5. Provide helpful error messages that guide users toward solutions

### Logging

Add detailed logging to aid in debugging:

1. Log all incoming and outgoing requests
2. Log the steps in tool registration and execution
3. Include payload information (but sanitize sensitive data)
4. Log errors with full context
5. Add correlation IDs to track related log messages

## Testing

Follow these testing practices to ensure at least 80% coverage:

1. **Unit testing**:
   - Every class and method should have unit tests
   - Test both success and failure paths
   - Test edge cases and error handling
   - Mock external dependencies

2. **Integration testing**:
   - Create tests with mocked communication
   - Create tests with real communication
   - Test end-to-end workflows
   - Test performance and timeouts

3. **Test coverage measurement**:
   - Run tests with coverage: `poetry run tox -e coverage`
   - Generate coverage reports: `poetry run pytest --cov=openmas.communication.mcp --cov-report=xml`
   - Review coverage regularly

4. **Continuous integration**:
   - Add coverage checks to CI pipeline
   - Set a minimum coverage threshold of 80%
   - Run both unit and integration tests in CI

Run the integration test with:

```bash
poetry run pytest tests/integration/mcp/real/test_openmas_mcp_sse.py -v --run-real-mcp
```

## Expected Outcome

After implementing these changes, you should have:

1. A fully functional MCP 1.7.1 SSE integration in OpenMAS
2. A clean, intuitive API that shields users from MCP protocol complexities
3. Robust internal handling of all edge cases and quirks
4. Comprehensive documentation focused on proper usage patterns
5. Passing integration tests with at least 80% test coverage
6. A clean implementation with no unnecessary complexity

The implementation will support all the key features of MCP 1.7.1:
- Server-Sent Events for communication
- Tool registration and calling
- Proper argument and response formatting
- Structured error handling
- All without exposing protocol complexities to users

## Additional Testing Scenarios

Based on the current implementation, more exhaustive testing is needed to fully understand all the real-world nuances of MCP 1.7.1. Consider implementing these additional test scenarios:

### 1. Concurrent Tool Calls Testing

Test how the system behaves under concurrent load when multiple clients call tools simultaneously.

**Test scenarios to implement:**
- Multiple clients calling the same tool concurrently
- Single client making multiple concurrent tool calls
- Mixed read/write operations under load
- Resource contention scenarios

### 2. Large Payload Testing

Test with large payloads to identify size limitations or performance degradation.

**Test scenarios to implement:**
- Text payloads of various sizes (1KB, 10KB, 100KB, 1MB)
- Structured payloads with nested objects of increasing depth
- Array payloads with many elements
- Binary data transmission of various sizes

### 3. Network Resilience Testing

Test disconnection/reconnection scenarios, especially with SSE which should handle reconnections.

**Test scenarios to implement:**
- Network interruption during tool call
- Server restart during active client connection
- Intermittent network connectivity
- Slow network conditions

### 4. Complex Argument Types Testing

Test with nested objects, arrays, and binary data.

**Test scenarios to implement:**
- Nested JSON objects of various depths
- Arrays with different element types
- Mixed types including numbers, booleans, null values
- Binary data in base64 encoding

### 5. Timeout Behavior Testing

Test various timeout scenarios.

**Test scenarios to implement:**
- Tool calls that take longer than the timeout
- Tool calls that hang indefinitely
- Cascading timeouts (one timeout triggering others)
- Recovery after timeout

These additional tests will help identify any remaining edge cases or performance concerns with the MCP 1.7.1 implementation.

## Implementation Strategy

1. **Start with Tests**:
   - Begin by implementing a comprehensive test suite.
   - Include additional tests that cover edge cases.

2. **Implement in Layers**:
   - First implement the core functionality with solid tests.
   - Then add the abstraction layer that shields users from MCP complexities.
   - Finally add comprehensive error handling and recovery mechanisms.

3. **User Experience First**:
   - Always design from the user's perspective - how should the API look to users?
   - Implement internal complexity handling to make the API simple and intuitive.
   - Document the public API thoroughly, not the internal workings.

4. **Continuous Integration**:
   - Ensure all tests pass on CI before considering the implementation complete.
   - Maintain the required 80% test coverage.
   - Add performance benchmarks to detect regressions.

## Conclusion

This implementation approach provides a clean, modern integration with MCP 1.7.1. By following Test-Driven Development principles and focusing on robust error handling, we ensure a high-quality, well-tested integration that addresses all the known issues in the current implementation.

The focus on user experience means developers using OpenMAS won't need to understand or work around MCP protocol details - they can focus on their business logic while the library takes care of the rest. This approach results in more maintainable user code and a better developer experience.

The comprehensive documentation updates focus on proper usage patterns rather than internal implementation details, ensuring that users can leverage the new functionality effectively without needing to understand the underlying complexities.

## References

- [MCP SDK Documentation](https://modelcontextprotocol.io/docs/)
- [FastMCP API Reference](https://python-sdk.modelcontextprotocol.ai/api/fastmcp/)
- [SSE Protocol Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [MCP 1.7.1 Release Notes](https://github.com/modelcontextprotocol/python-sdk/releases)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/en/latest/)
- [Test-Driven Development Guide](https://testdriven.io/test-driven-development/)
- [API Design Principles](https://www.oreilly.com/content/how-to-design-a-good-api-why-it-matters/)
- [User Experience in API Design](https://nordicapis.com/creating-good-api-user-experience/)
- MCP python-sdk source code locally available in /Users/wilson/Coding/python-sdk-1.7.1
