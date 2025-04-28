# MCP Integration Testing

This directory contains a comprehensive suite of integration tests for the Model Context Protocol (MCP) functionality in OpenMAS, following the MCP Integration Testing Improvement Plan.

## Implemented Test Phases

The following phases have been implemented:

### Phase 1: Enhanced Test Harness
- `McpTestHarness` class in `test_utils.py` provides standardized process management and verification
- Supports both stdio and SSE transport types
- Implements incremental verification methods
- Ensures robust cleanup
- Provides structured verification methods
- Includes detailed logging for debugging

### Phase 2: Complete Tool Call Testing
- `test_stdio_tool_calls.py`: Tests tool calls via stdio transport
- `test_sse_tool_calls.py`: Tests tool calls via SSE transport
- Tests multiple consecutive tool calls
- Verifies response parsing and error handling
- Tests with various parameters

### Phase 3: Error Handling and Recovery Testing
- `test_error_handling.py`: Tests robustness against common failure scenarios
- Tests connection failures (server not available)
- Tests malformed requests and invalid parameters
- Tests timeouts at various stages
- Tests reconnection after server restart
- Tests proper cleanup during asyncio cancellation

### Phase 4: End-to-End Agent Testing
- `test_e2e_agents.py`: Tests complete agent-to-agent communication
- Tests client-server communication between actual agents
- Tests multiple tools being called in sequence
- Tests complex data structures in requests/responses
- Tests bidirectional communication
- Tests multiple clients connecting to a single server

### Phase 5: Integration with Agent Patterns
- Tests MCP communication within agent lifecycle methods
- Tests tool execution in response to messages
- Tests agent-to-agent coordination

## Test Structure

1. **Basic Functionality Tests**
   - `test_stdio_test_only_mode`: Tests stdio server in test-only mode
   - `test_sse_test_only_mode`: Tests SSE server in test-only mode

2. **Server Startup and Verification Tests**
   - `test_stdio_server_startup`: Tests stdio server initialization and connectivity
   - `test_sse_server_startup`: Tests SSE server initialization and connectivity

3. **Tool Call Tests**
   - `test_stdio_echo_tool_call`: Tests calling the echo tool via stdio
   - `test_sse_echo_tool_call`: Tests calling the echo tool via SSE
   - `test_stdio_multiple_tool_calls`: Tests multiple consecutive tool calls
   - `test_sse_multiple_tool_calls`: Tests multiple consecutive tool calls

4. **Agent Integration Tests**
   - `test_stdio_with_agent`: Tests using an agent with McpStdioCommunicator
   - `test_sse_with_agent`: Tests using an agent with McpSseCommunicator
   - `test_stdio_agent_multiple_tool_calls`: Tests multiple tool calls from an agent
   - `test_sse_agent_multiple_tool_calls`: Tests multiple tool calls from an agent

5. **Error Handling Tests**
   - `test_server_not_available_stdio`: Tests handling when stdio server not available
   - `test_server_not_available_sse`: Tests handling when SSE server not available
   - `test_malformed_tool_call_stdio`: Tests handling of malformed stdio tool calls
   - `test_malformed_tool_call_sse`: Tests handling of malformed SSE tool calls
   - `test_timeout_handling_stdio`: Tests timeout handling for stdio
   - `test_timeout_handling_sse`: Tests timeout handling for SSE
   - `test_cancellation_handling_stdio`: Tests cancellation handling for stdio
   - `test_cancellation_handling_sse`: Tests cancellation handling for SSE
   - `test_server_restart_recovery_stdio`: Tests reconnection after server restart

6. **End-to-End Agent Tests**
   - `test_e2e_basic_communication`: Tests basic agent-to-agent communication
   - `test_e2e_bidirectional_communication`: Tests bidirectional agent communication
   - `test_e2e_multi_agent_communication`: Tests multiple agents communicating

## Using the Test Harness

The `McpTestHarness` class provides common functionality for testing MCP server processes:

```python
# Create a test harness for stdio transport
harness = McpTestHarness(transport_type=TransportType.STDIO)

# Create a test harness for SSE transport with a specific port
harness = McpTestHarness(
    transport_type=TransportType.SSE,
    test_port=8765,
)

# Start the server
process = await harness.start_server(test_only=False)

# Verify server startup
startup_verified = await harness.verify_server_startup()

# Verify basic connectivity
connectivity_verified = await harness.verify_basic_connectivity()

# Get verification results
verification_summary = harness.get_verification_summary()

# Clean up
await harness.cleanup()
```

## Running the Tests

To run the MCP integration tests:

```bash
# Run all MCP tests
tox -e py310-mcp

# Run a specific test file
tox -e py310-mcp -- tests/integration/mcp/test_stdio_tool_calls.py

# Run a specific test function with verbose output
tox -e py310-mcp -- tests/integration/mcp/test_e2e_agents.py::test_e2e_basic_communication -v
```

## Writing New Tests

When creating new MCP integration tests:

1. Use the `McpTestHarness` class for managing server processes.
2. Follow the incremental verification pattern:
   - First verify server startup
   - Then verify basic connectivity
   - Then test specific functionality
3. Use proper cleanup in a `try/finally` block.
4. Add appropriate assertions and detailed error messages.
5. For SSE tests, use random ports to avoid conflicts.
6. Include appropriate markers, such as `@pytest.mark.mcp`.
7. Skip tests that require optional dependencies when appropriate.

### Example: Testing a New Feature

```python
@pytest.mark.asyncio
@pytest.mark.mcp
async def test_my_new_feature_stdio():
    """Test my new feature using stdio transport."""
    harness = McpTestHarness(TransportType.STDIO)

    try:
        # Start the server
        process = await harness.start_server()
        assert process.returncode is None, "Process failed to start"

        # Verify server startup
        startup_verified = await harness.verify_server_startup()
        assert startup_verified, "Server startup verification failed"

        # Create client using stdio transport
        script_path = str(harness.script_path)
        params = StdioServerParameters(command=sys.executable, args=[script_path])

        async with stdio_client(params) as streams:
            read_stream, write_stream = streams

            # Create and initialize session
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=5.0)
                await asyncio.sleep(1.0)  # Wait for initialization

                # Test your feature
                result = await session.call_tool("my_feature", {"param": "value"})
                assert result.get("expected_key") == "expected_value"

    finally:
        await harness.cleanup()
```

## Implementation Guidelines

### Transport-Specific Considerations

#### stdio Transport
- Ensures the script is executable (`chmod 0o755`)
- Uses `asyncio.subprocess.PIPE` for both stdout and stderr
- Verifies the process by reading from stderr
- Reads test messages from stdout

#### SSE Transport
- Uses random ports to avoid conflicts
- Extracts the server URL from stderr output
- Tests HTTP connectivity before attempting MCP operations
- Skips tests when aiohttp is not available

### Error Handling Best Practices

1. Always use timeouts for all network and process operations
2. Use `try/finally` blocks to ensure cleanup
3. Shield cleanup operations from cancellation:
   ```python
   try:
       await asyncio.shield(harness.cleanup())
   except Exception as e:
       logger.warning(f"Error during cleanup: {e}")
   ```
4. Log warnings instead of failing tests on non-critical issues
5. Add skip conditions for missing optional dependencies
