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

## Testing

The example includes a test file (`test_example.py`) that demonstrates how to test MCP tool calls using the OpenMAS testing utilities:

- `AgentTestHarness`: For creating and managing the agent lifecycle
- `expect_request`: For setting up expectations for the tool call
- `multi_running_agents`: For managing multiple agents in the test

## Additional Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/concepts/tools)
- [OpenMAS MCP Integration Guide](../../guides/mcp_integration.md)
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
