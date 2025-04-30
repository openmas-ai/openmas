# Welcome to OpenMAS

**OpenMAS** is a lightweight Python SDK designed for building asynchronous Multi-Agent Systems (MAS) with a strong focus on leveraging the Model Context Protocol (MCP) for efficient and standardized agent-model communication.

It aims to provide developers with the essential tools and patterns to create sophisticated, independent agents that can communicate, coordinate, and interact with various AI models and services.

## Key Features

*   **Flexible Agent Framework:** Build agents using the `BaseAgent` class with clear lifecycle methods (`setup`, `run`, `shutdown`).
*   **Diverse Communication:** Support for HTTP, WebSockets, gRPC, and MQTT alongside first-class MCP integration.
*   **Environment Configuration:** Easily configure agents via environment variables or configuration files.
*   **Testing Utilities:** Includes tools like `MockCommunicator` and `AgentTestHarness` to facilitate testing your agent applications.
*   **Deployment Ready:** Tools to help package and deploy your agent systems.

## Getting Started

Ready to build your first agent? Follow these steps:

1.  **Installation:** Get OpenMAS installed in your environment.
    [Go to Installation Guide](installation.md)
2.  **Quick Start:** Walk through a simple example to create and run a basic agent.
    [Go to Getting Started Guide](getting_started.md)

## Explore Further

*   **Core Concepts:** Understand the fundamental ideas behind OpenMAS.
    *   [Design Philosophy](design.md)
    *   [Architecture Overview](architecture.md)
*   **Guides:** Learn how to use specific features.
    *   [Using Testing Utilities](testing-utilities.md)
    *   [Integrating with LLMs](llm_integration.md)
    *   [Using MCP](mcp_integration.md)
*   **API Reference:** Detailed documentation for all modules and classes.
    [Go to API Reference](api_reference.md)
*   **Command Line Interface:** Learn about the `openmas` CLI tool.
    [Go to CLI Docs](cli/index.md)
