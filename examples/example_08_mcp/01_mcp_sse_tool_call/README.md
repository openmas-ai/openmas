# MCP Tool Call over SSE Example

This example demonstrates how to use MCP (Model Context Protocol) tool calls over Server-Sent Events (SSE) in OpenMAS. It showcases how one agent can define an MCP tool and another agent can call that tool, with the communication happening over an HTTP-based SSE connection.

## Key Concepts

- **MCP Tools**: A mechanism for agents to expose functionality to be called by other agents, similar to a function or API endpoint.
- **SSE Communication**: The agents communicate using Server-Sent Events over HTTP, which enables real-time, one-way communication that works well for asynchronous tool calls.
- **Tool Registration**: One agent (the provider) registers a tool that can be called by the other agent.
- **Tool Calling**: Another agent (the user) calls the registered tool and processes the response.

## Architecture

This example consists of two agents:

1. **ToolProviderAgent**:
   - Runs with the HTTP communicator in server mode
   - Registers a tool called "process_data" that can transform text input
   - Processes incoming tool calls and returns results

2. **ToolUserAgent**:
   - Runs with the McpSseCommunicator in client mode
   - Connects to the tool provider agent over SSE
   - Calls the "process_data" tool with a text payload
   - Processes and displays the result

## Choosing Between MCP Transports

MCP supports multiple transport mechanisms for communication between agents. This example uses the SSE transport:

### Server-Sent Events (SSE) Transport

**Best for:**
- Web-based applications
- Real-time data streaming to clients
- Push notifications
- Asynchronous, one-way communication
- Distributed systems across networks

**Advantages:**
- Works over standard HTTP - no special protocols required
- Automatic reconnection handling
- Can traverse firewalls and proxies easily
- Better for real-time updates than polling
- Lightweight compared to WebSockets

**Limitations:**
- One-way communication (server to client)
- Limited to HTTP/HTTPS
- Some connection limits in certain browsers
- May require specific configuration for load balancers

## How to Run This Example

You can run this example using the OpenMAS CLI:

```bash
# Navigate to the example directory
cd examples/example_08_mcp/01_mcp_sse_tool_call

# Run the tool provider agent (in one terminal)
openmas run tool_provider

# Run the tool user agent (in another terminal)
openmas run tool_user
```

Alternatively, you can run both agents together:

```bash
openmas run tool_provider tool_user
```

## Expected Output

When running both agents, you should see output similar to:

```
[INFO] ToolProviderAgent: Setting up ToolProviderAgent
[INFO] ToolProviderAgent: Registered MCP tool: process_data
[INFO] ToolProviderAgent: ToolProviderAgent setup complete
[INFO] ToolProviderAgent: ToolProviderAgent running, waiting for tool calls

[INFO] ToolUserAgent: Setting up ToolUserAgent
[INFO] ToolUserAgent: ToolUserAgent setup complete
[INFO] ToolUserAgent: ToolUserAgent running, calling process_data tool
[INFO] ToolUserAgent: Calling tool 'process_data' with payload: {'text': 'Hello, this is a sample text that needs processing.'}
[INFO] ToolProviderAgent: Tool handler received data: {'text': 'Hello, this is a sample text that needs processing.'}
[INFO] ToolProviderAgent: Tool handler returning result: {'processed_text': 'HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.', 'word_count': 9, 'status': 'success'}
[INFO] ToolUserAgent: Received tool result: {'processed_text': 'HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.', 'word_count': 9, 'status': 'success'}
[INFO] ToolUserAgent: Successfully processed text. Word count: 9
[INFO] ToolUserAgent: Processed text: HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.
[INFO] ToolUserAgent: ToolUserAgent completed its run method
```

## Code Explanation

### Tool Provider Agent

```python
# Register the process_data tool with the MCP communicator
await self.communicator.register_tool(
    name="process_data",
    description="Process incoming data and return a result",
    function=self.process_data_handler
)

# Tool handler function
async def process_data_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Process the incoming data and return a result
    processed_text = payload["text"].upper()
    word_count = len(payload["text"].split())

    return {
        "processed_text": processed_text,
        "word_count": word_count,
        "status": "success"
    }
```

### Tool User Agent

```python
# Call the process_data tool provided by the tool_provider agent
result = await self.communicator.call_tool(
    target_service="tool_provider",
    tool_name="process_data",
    arguments={"text": "Hello, this is a sample text that needs processing."},
    timeout=timeout_seconds
)

# Process the result
if result.get("status") == "success":
    logger.info(f"Successfully processed text. Word count: {result.get('word_count')}")
    logger.info(f"Processed text: {result.get('processed_text')}")
```

### Configuration

The `openmas_project.yml` file configures:

1. The tool provider to use the HTTP communicator in server mode
2. The tool user to use the McpSseCommunicator in client mode
3. The service URL for the tool user to find the tool provider

## Troubleshooting MCP SSE Connections

If you encounter issues with MCP communication over SSE, here are some common problems and solutions:

### Common Issues

1. **Connection Refused**:
   - **Symptom**: "Connection refused" errors when the client tries to connect
   - **Cause**: The server may not be running or the port is different
   - **Solution**: Ensure the tool provider is running and the port matches in the service URL

2. **Service URL Issues**:
   - **Symptom**: "Service not found" errors
   - **Cause**: Incorrect service URL format in the project configuration
   - **Solution**: Ensure the service URL is in the format `http://hostname:port`

3. **Tool Name Mismatch**:
   - **Symptom**: "Tool not found" errors
   - **Cause**: The user agent is calling a tool with a different name than what's registered
   - **Solution**: Ensure the tool name in `register_tool()` matches exactly what's used in `call_tool()`

4. **CORS Issues**:
   - **Symptom**: "CORS policy" errors in browser console
   - **Cause**: Cross-Origin Resource Sharing restrictions when running in a browser
   - **Solution**: If using in a browser context, configure the server with appropriate CORS headers

### Debugging Tips

1. **Enable Debug Logging**:
   ```python
   # In your project configuration
   default_config:
     log_level: DEBUG
   ```

2. **Use Network Tools**:
   - Tools like `curl` or Postman can help debug HTTP/SSE connections
   - Example: `curl -N http://localhost:8000/sse`

3. **Monitor HTTP Traffic**:
   - Use tools like Wireshark or the browser's network inspector to see the SSE traffic

4. **Check Server Status**:
   - Verify the server is running and listening on the expected port:
   ```bash
   curl http://localhost:8000/health
   ```

## Testing

The example includes a test file (`test_example.py`) that demonstrates how to test MCP tool calls using the OpenMAS testing utilities:

- `AgentTestHarness`: For creating and managing the agent lifecycle
- `expect_request`: For setting up expectations for the tool call
- `multi_running_agents`: For managing multiple agents in the test

## Additional Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/concepts/tools)
- [OpenMAS MCP Integration Guide](../../guides/mcp_integration.md)
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [SSE Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
