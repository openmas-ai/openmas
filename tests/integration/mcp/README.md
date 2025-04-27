# MCP Integration Tests

This directory contains integration tests for the Model Context Protocol (MCP) functionality in OpenMAS.

## Test Approach

The MCP integration tests are designed to validate the interaction between OpenMAS agents and MCP services. The tests are organized in a progressive manner, with each test building on the previous ones to ensure robust validation.

### Test Structure

1. **Basic Functionality Tests**
   - `test_direct_stdio_server`: Tests that the stdio server script can start correctly and respond to basic commands.

2. **Real Integration Tests**
   - `test_real_stdio_integration`: Tests the full integration between an MCP client agent and server over stdio. This test incrementally verifies:
     - Server subprocess successfully launches
     - The server process initializes correctly
     - Basic communication is established
     - Proper cleanup occurs when the test is complete

3. **Mock Tests**
   - `test_mock_agent.py`: Uses mock communicators to test MCP agent interactions without real dependencies.
   - `test_mock_client_server.py`: Tests client-server interactions using mocked components.

## Test Files

- `stdio_server_script.py`: A server script that implements a simple MCP server for testing. It provides an "echo" tool for basic functionality tests.
- `test_real_stdio_integration.py`: Contains tests for real stdio-based communication.
- `test_real_mcp_basic.py`: Contains basic tests for MCP functionality.
- `test_mock_agent.py` and `test_mock_server_agent.py`: Contains tests using mock implementations.

## Running Tests

To run the MCP integration tests:

```bash
# Run all MCP tests
tox -e py310-mcp

# Run a specific test file
tox -e py310-mcp -- tests/integration/mcp/test_real_stdio_integration.py

# Run a specific test function with verbose output
tox -e py310-mcp -- tests/integration/mcp/test_real_stdio_integration.py::test_real_stdio_integration -v
```

## Implementation Notes

### Asynchronous Communication Challenges

MCP integration tests involve complex asynchronous communication between processes. Some key challenges addressed in these tests include:

1. **Pipe Communication**: The stdio server communicates over standard input/output pipes, which requires careful handling to avoid deadlocks.

2. **Initialization Timing**: The most common error when working with MCP is timing issues related to initialization. The tests explicitly:
   - Wait for the server to start
   - Initialize sessions explicitly
   - Add delays where necessary to ensure proper synchronization

3. **Cancellation Handling**: The tests handle asyncio cancellation carefully to ensure proper cleanup of processes and resources.

4. **Robust Error Handling**: Clear error messages are logged to help diagnose communication failures.

5. **Incremental Testing**: The tests are designed to validate each step of the communication process separately before testing the full integration.

### Breaking Down the Test Approach

Rather than attempting to test the entire MCP stack in one go, the integration tests break down the testing into manageable, isolation-friendly components:

1. Testing basic process startup
2. Testing simple message exchange
3. Testing full MCP initialization
4. Testing tool calls

This approach makes it easier to diagnose issues when they occur.
