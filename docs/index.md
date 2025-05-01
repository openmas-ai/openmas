# Welcome to OpenMAS

**OpenMAS** is a lightweight Python SDK designed for building asynchronous Multi-Agent Systems (MAS) with a strong focus on leveraging the Model Context Protocol (MCP) for efficient and standardized agent-model communication.

It aims to provide developers with the essential tools and patterns to create sophisticated, independent agents that can communicate, coordinate, and interact with various AI models and services.

## Key Features

*   **Flexible Agent Design:** Build agents using the `BaseAgent` class with a clean lifecycle pattern, supporting various reasoning frameworks (BDI, LLM-based, heuristics).
*   **Diverse Communication:** First-class support for [Model Context Protocol](https://modelcontextprotocol.io/introduction) alongside with HTTP, WebSockets, gRPC, and MQTT.
*   **Extensible Architecture:** Customize with local extensions or reusable packages, all with lazy loading to keep the core lightweight.
*   **Powerful Configuration:** Multi-layered system supporting environment variables, .env files, and YAML configuration.
*   **Project Structure & CLI:** Opinionated project organization with a command-line interface for scaffolding, validation, execution, and deployment.
*   **Testing & Deployment:** Includes testing utilities and tools to automatically generate Docker artifacts for your agent systems.

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
