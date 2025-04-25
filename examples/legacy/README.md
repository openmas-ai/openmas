# OpenMAS Examples

This directory contains examples demonstrating how to use the OpenMAS framework. Each example illustrates different aspects of the framework and can be used as a reference for building your own agent-based systems.

## Getting Started

All examples can be run using Poetry:

```bash
# Install dependencies
poetry install

# Run an example
poetry run python examples/basic/hello_world.py
```

## Example Categories

### Basic Examples

Simple examples showing the core functionality:

- **[hello_world.py](basic/hello_world.py)**: Basic agent creation and message passing
- **Other basic examples**: Check the `basic/` directory for more fundamental examples

### Communication Examples

Examples demonstrating different communication methods:

- **[grpc_example.py](communication/grpc_example.py)**: Using gRPC for agent communication
- **MCP (Model Context Protocol)**: Examples for MCP integration in the `mcp/` directory

### Advanced Patterns

Advanced agent design patterns:

- **[bdi_agent_example.py](patterns/bdi_agent_example.py)**: Belief-Desire-Intention agent architecture
- **[orchestrator_worker_example.py](patterns/orchestrator_worker_example.py)**: Orchestrator-worker pattern

### LLM Integration

Examples showing LLM integration:

- **[llm_agent.py](mcp/llm_agent.py)**: Integrating LLMs via MCP
- **[external_mcp_server.py](mcp/external_mcp_server.py)**: Connecting to external MCP servers

### Deployment

Examples for deploying agents in different environments:

- **[Dockerfile](Dockerfile)**: Docker deployment example
- **[docker-compose.yml](docker-compose.yml)**: Multi-container deployment

## Example Directory Structure

```
examples/
├── basic/                # Basic examples for getting started
├── communication/        # Communication-focused examples
│   ├── grpc/            # gRPC communication
│   └── mcp/             # MCP communication
├── deployment/           # Deployment examples
├── integrations/         # Integration with external services
├── llm_service/          # LLM service integration
├── mcp/                  # MCP-specific examples
├── multi-agent/          # Multi-agent system examples
├── patterns/             # Design pattern examples
└── README.md             # This file
```

## Running the Examples

Each example includes documentation at the top of the file explaining:
- What the example demonstrates
- How to run it
- Any prerequisites or environment setup required

## MCP Examples

The Model Context Protocol (MCP) examples demonstrate how to integrate LLMs into agent systems. To run these examples:

1. Set up your environment:
   ```bash
   export ANTHROPIC_API_KEY=your_api_key
   ```

2. Run an MCP server (for some examples):
   ```bash
   poetry run mcp-server
   ```

3. Run the example:
   ```bash
   poetry run python examples/mcp/llm_agent.py
   ```

See [README_MCP.md](README_MCP.md) for more details on MCP integration.

## Creating Your Own Examples

When creating your own examples based on these templates:

1. Follow the structure and patterns demonstrated
2. Include clear documentation at the top of each file
3. Use descriptive names for classes and methods
4. Add necessary error handling
5. Include logging for better understanding of the flow

## Testing Examples

Run the examples with increased logging for debugging:

```bash
poetry run python examples/basic/hello_world.py --log-level=DEBUG
```

## Contributing

If you create a useful example, consider contributing it back to the project by:
1. Following the existing code style
2. Adding thorough documentation
3. Including test cases
4. Submitting a pull request
