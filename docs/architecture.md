# OpenMAS Architecture

OpenMAS is designed with a modular and extensible architecture to simplify the creation and management of Multi-Agent Systems (MAS).

## Core Philosophy

Before diving into components, understanding the core principles helps:

*   **Simplicity & Composability:** Use simple building blocks.
*   **Modularity & Pluggability:** Easily extend with new communication methods or agent patterns.
*   **Separation of Concerns:** Isolate agent logic, communication, configuration, and deployment.
*   **Agent Reasoning Agnosticism:** The framework provides the agent's structure, not its internal decision-making logic.

(See the full [Design Philosophy](design.md) for more details).

## Key Components

### 1. `BaseAgent` (`openmas.agent.BaseAgent`)

This is the fundamental building block for any entity within an OpenMAS system. All agents inherit from `BaseAgent`.

*   **Responsibilities:**
    *   Manages the agent's lifecycle.
    *   Handles configuration loading.
    *   Holds a reference to the agent's communicator.
    *   Provides basic properties like `name`, `config`, `communicator`, `logger`.
*   **Lifecycle Methods:** Defines standard asynchronous methods that developers override:
    *   `async setup()`: Called once when the agent starts. Used for initialization, loading resources, registering handlers, etc.
    *   `async run()`: The main execution logic loop of the agent. Called after `setup()` completes.
    *   `async shutdown()`: Called once when the agent stops gracefully. Used for cleanup (e.g., closing connections).
*   **Starting/Stopping:** The lifecycle is managed via `await agent.start()` (which runs `setup` then `run`) and `await agent.stop()` (which runs `shutdown`).

### 2. `BaseCommunicator` (`openmas.communication.base.BaseCommunicator`)

This abstract base class defines the interface for all communication methods within OpenMAS. It decouples agent logic from the specifics of network protocols.

*   **Responsibilities:**
    *   Sending requests to other services/agents (`send_request`).
    *   Sending notifications (fire-and-forget messages) (`send_notification`).
    *   Registering handlers for incoming requests (`register_handler`).
    *   Managing the underlying communication channels (e.g., starting/stopping HTTP servers or client connections).
*   **Implementations:** OpenMAS provides concrete implementations for various protocols:
    *   `HttpCommunicator`
    *   `McpSseCommunicator`
    *   `McpStdioCommunicator`
    *   `GrpcCommunicator`
    *   `MqttCommunicator`
*   **Selection:** The specific communicator used by an agent is determined by its configuration (`communicator_type` and `communicator_options`) and instantiated automatically by `BaseAgent`, or can be set manually using `agent.set_communicator()`.

### 3. Configuration System (`openmas.config`)

OpenMAS uses a layered configuration system to manage settings for agents and communicators.

*   **Sources:** Loads settings from environment variables, `.env` files, project YAML (`openmas_project.yml`), and environment-specific YAML files (`config/*.yml`).
*   **Loading:** Uses the `load_config()` function with Pydantic models (like `AgentConfig` or custom subclasses) for validation and type-safe access.
*   **Access:** Configuration is accessible within the agent via `self.config`.

(See the [Configuration Guide](guides/configuration.md) for details).

### 4. Logging (`
