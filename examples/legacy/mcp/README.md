# MCP (Model Context Protocol) Examples

This directory contains examples of integrating Large Language Models (LLMs) into SimpleMAS using MCP (Model Context Protocol). These examples demonstrate advanced techniques for using LLMs as part of agent systems.

## Examples

### LLM Agent Example

[llm_agent.py](llm_agent.py) - Demonstrates creating an agent that uses an LLM for natural language interactions. This example shows:
- Connecting to a MCP server
- Sending prompts to an LLM model
- Processing responses in an agent system
- Handling asynchronous LLM requests

To run:
```bash
export ANTHROPIC_API_KEY=your_api_key
poetry run python examples/mcp/llm_agent.py
```

### External MCP Server Example

[external_mcp_server.py](external_mcp_server.py) - Shows how to connect agents to an external MCP server. This example demonstrates:
- Setting up agents with MCP communicators
- Connecting to an external MCP server
- Sending and receiving messages via MCP

To run:
```bash
# Option 1: Run with a local MCP server
poetry run python -m mcp.server.fastmcp
# In another terminal:
poetry run python examples/mcp/external_mcp_server.py

# Option 2: Connect to a remote MCP server
export MCP_SERVER_URL=https://your-mcp-server.com
poetry run python examples/mcp/external_mcp_server.py
```

## Prerequisites

To run these examples, you'll need:

1. An Anthropic API key for Claude models (set as `ANTHROPIC_API_KEY` environment variable)
2. The MCP package installed (`poetry install mcp`)
3. For some examples, a running MCP server (either local or remote)

## MCP Server

The MCP server is the intermediary that handles communication between the SimpleMAS agents and the LLM services.

To run a local MCP server:
```bash
poetry run python -m mcp.server.fastmcp
```

This will start a server on `http://localhost:8000` by default.

## Advanced Examples

These examples demonstrate more advanced MCP integration patterns:

- Tool usage by LLMs
- Streaming responses
- Multi-agent LLM coordination
- Maintaining conversation context across interactions

## Related Resources

- [Anthropic Python SDK Documentation](https://github.com/anthropics/anthropic-sdk-python)
- [FastMCP Documentation](https://github.com/anthropics/anthropic-tools/tree/main/mcp)
- [Claude API Documentation](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
