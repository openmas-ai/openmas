# MCP Tool Call over stdio Example

This example demonstrates how to use MCP (Model Context Protocol) tool calls over standard input/output (stdio) in OpenMAS. It showcases how one agent can define an MCP tool and another agent can call that tool, with the communication happening over stdio streams.

## Key Concepts

- **MCP Tools**: A mechanism for agents to expose functionality to be called by other agents, similar to a function or API endpoint.
- **stdio Communication**: The agents communicate using standard input/output streams, which enables interprocess communication without network overhead.
- **Tool Registration**: One agent (the provider) registers a tool that can be called by the other agent.
- **Tool Calling**: Another agent (the user) calls the registered tool and processes the response.

## Architecture

This example consists of two agents:

1. **ToolProviderAgent**:
   - Runs in server mode with the McpStdioCommunicator
   - Registers a tool called "process_data" that can transform text input
   - Processes incoming tool calls and returns results

2. **ToolUserAgent**:
   - Runs in client mode with the McpStdioCommunicator
   - Connects to the tool provider agent
   - Calls the "process_data" tool with a text payload
   - Processes and displays the result

## Choosing Between MCP Transports

MCP supports multiple transport mechanisms for communication between agents. The two most common are:

### stdio Transport (This Example)

**Best for:**
- Local inter-process communication
- Child process tool providers
- Simple deployment scenarios
- Development and testing
- Situations where network setup would be complex

**Advantages:**
- No network configuration required
- Lower overhead than HTTP-based transports
- Simple process-based isolation
- Works well for parent-child process relationships
- No port conflicts or firewall issues

**Limitations:**
- Limited to processes on the same machine
- Cannot scale across network boundaries
- Less flexible for dynamic discovery
- Requires careful process management

### SSE Transport (Server-Sent Events)

**Best for:**
- Distributed agent systems
- Multi-machine deployments
- Cloud-based environments
- Systems requiring horizontal scaling
- Public-facing agent services

**Advantages:**
- Works across network boundaries
- Can be load-balanced
- Supports many concurrent connections
- More discoverable (via HTTP endpoints)
- Better suited for containerized environments

**Limitations:**
- Requires network configuration
- Additional HTTP overhead
- More complex setup and security considerations
- Potential port conflicts

**Choose stdio transport when:** You need simple, local communication between processes without network complexity.

**Choose SSE transport when:** You need distributed agents communicating across network boundaries or in cloud environments.

## Running the Example

To run this example, you'll need to have OpenMAS installed with the MCP extras:

```bash
pip install "openmas[mcp]"
```

Then, you can run the example using the OpenMAS CLI:

```bash
cd examples/example_02_mcp/02_mcp_stdio_tool_call
openmas run
```

This will start both agents and you'll see the logs showing the tool registration, call, and response.

## Expected Output

When you run the example, you should see output similar to this:

```
INFO     Setting up ToolProviderAgent
INFO     Registering MCP tool: process_data
INFO     ToolProviderAgent setup complete, tool registered
INFO     ToolProviderAgent running, waiting for tool calls
INFO     Setting up ToolUserAgent
INFO     ToolUserAgent setup complete
INFO     ToolUserAgent running, calling process_data tool
INFO     Calling tool 'process_data' with payload: {'text': 'Hello, this is a sample text that needs processing.'}
INFO     Tool handler received data: {'text': 'Hello, this is a sample text that needs processing.'}
INFO     Tool handler returning result: {'processed_text': 'HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.', 'word_count': 9, 'status': 'success'}
INFO     Received tool result: {'processed_text': 'HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.', 'word_count': 9, 'status': 'success'}
INFO     Successfully processed text. Word count: 9
INFO     Processed text: HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.
INFO     ToolUserAgent completed its run method
```

## Communication Flow

The following sequence diagram illustrates the communication flow between the ToolUserAgent and ToolProviderAgent:

```
┌─────────────┐                     ┌─────────────┐
│ ToolUserAgent│                     │ToolProviderAgent│
└──────┬──────┘                     └───────┬─────┘
       │                                    │
       │                                    │
       │                                    │ setup()
       │                                    │ ┌─┐
       │                                    │ │ │ register_tool("process_data")
       │                                    │ │ │
       │                                    │ └─┘
       │                                    │
       │ run()                              │
       │ ┌─┐                                │
       │ │ │ call_tool("process_data")      │
       │ │ │ -------------------------------->
       │ │ │                                │ process_data_handler()
       │ │ │                                │ ┌─┐
       │ │ │                                │ │ │ process payload
       │ │ │                                │ │ │ prepare response
       │ │ │                                │ └─┘
       │ │ │                                │
       │ │ │ response                       │
       │ │ │ <--------------------------------
       │ │ │ process response               │
       │ │ │ display results                │
       │ └─┘                                │
       │                                    │
┌──────┴──────┐                     ┌───────┴─────┐
│ ToolUserAgent│                     │ToolProviderAgent│
└─────────────┘                     └─────────────┘
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
    arguments={"text": "Hello, this is a sample text that needs processing."}
)

# Process the result
if result.get("status") == "success":
    print(f"Successfully processed text. Word count: {result.get('word_count')}")
    print(f"Processed text: {result.get('processed_text')}")
```

### Configuration

The `openmas_project.yml` file configures:

1. The tool provider to use the McpStdioCommunicator in server mode
2. The tool user to use the McpStdioCommunicator in client mode
3. The service URL for the tool user to find the tool provider

## Troubleshooting MCP Connections

If you encounter issues with MCP communication over stdio, here are some common problems and solutions:

### Common Issues

1. **Initialization Timeout**:
   - **Symptom**: Tool calls hang or time out during initialization
   - **Cause**: The provider agent may not be properly starting or registering tools
   - **Solution**: Check that both agents are starting correctly and the provider is registering the tool with exactly the same name the user is calling

2. **Service URL Issues**:
   - **Symptom**: "Service not found" errors
   - **Cause**: Incorrect service URL format in the project configuration
   - **Solution**: For stdio, service URLs should be prefixed with "stdio:" followed by a command or executable path

3. **Tool Name Mismatch**:
   - **Symptom**: "Tool not found" errors
   - **Cause**: The user agent is calling a tool with a different name than what's registered
   - **Solution**: Ensure the tool name in `register_tool()` matches exactly what's used in `call_tool()`

4. **Serialization Errors**:
   - **Symptom**: Error messages about invalid JSON or serialization failures
   - **Cause**: Tool arguments or return values aren't properly serializable
   - **Solution**: Ensure all data passed to and from tools is JSON-serializable

### Debugging Tips

1. **Enable Debug Logging**:
   ```python
   # In your project configuration
   default_config:
     log_level: DEBUG
   ```

2. **Check Stderr Output**:
   - MCP stdio communicator uses stderr for logging, so check stderr output for error messages
   - A common pattern is server processes printing "ready" signals to stderr

3. **Use the MCP Inspector**:
   ```bash
   # Install MCP with CLI tools
   pip install "mcp[cli]"
   # Run the inspector on your server
   mcp dev --stdio-command "openmas run tool_provider"
   ```

4. **Manual Process Testing**:
   Run the provider agent separately and note the output for any error messages:
   ```bash
   openmas run tool_provider --log-level=DEBUG
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
