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

(See the [Configuration Guide](configuration.md) for details).

### 4. Logging (`openmas.logging`)

Provides standardized logging setup (`configure_logging`) and access (`get_logger`).

## Conceptual Diagram

```mermaid
graph TD
    subgraph Agent [Your Agent Instance (inherits BaseAgent)]
        direction LR
        Logic[Agent Logic (in run(), handlers)]
        Lifecycle(Lifecycle Mgmt setup/run/shutdown)
        Config(self.config)
        CommRef(self.communicator)
    end

    subgraph OpenMAS Core
      BaseAgentClass[BaseAgent Class]
      BaseCommClass[BaseCommunicator Class]
      ConfigSystem[Configuration System]
      LoggingSystem[Logging System]
    end

    subgraph Communicator [Communicator Instance (e.g., HttpCommunicator)]
       direction LR
       SendRecv(Send/Receive Logic)
       HandlerReg(Handler Registry)
       ProtocolImpl(Protocol Implementation e.g., HTTP Server/Client)
    end

    subgraph External World
        OtherAgent[Other Agent / Service]
        MCPService[MCP Service]
        Database[Database / Other Resource]
    end

    BaseAgentClass -- Inherited By --> Agent
    Agent -- Uses --> ConfigSystem
    Agent -- Uses --> LoggingSystem
    Agent -- Holds Reference --> CommRef
    CommRef -- Instance Of --> BaseCommClass
    CommRef -- Is A --> Communicator

    Communicator -- Interacts With --> External World
    Logic -- Calls --> CommRef
    Lifecycle -- Manages --> Logic
    ConfigSystem -- Populates --> Config
    LoggingSystem -- Provides --> Agent(self.logger)
```

**Explanation:**

1.  You create an agent class inheriting from `BaseAgent`.
2.  When you instantiate and `start()` your agent:
    *   `BaseAgent` uses the `Configuration System` to load settings into `self.config`.
    *   Based on the config, `BaseAgent` instantiates a specific `Communicator` (e.g., `HttpCommunicator`) which implements `BaseCommunicator`.
    *   The agent holds this instance as `self.communicator`.
    *   The agent's `setup()` and `run()` methods execute, containing your custom logic.
3.  Your agent logic interacts with the outside world by calling methods on `self.communicator` (e.g., `send_request`, `register_handler`).
4.  The `Communicator` instance handles the protocol-specific details of sending messages or routing incoming messages to registered handlers.

This architecture allows you to focus on your agent's logic while leveraging the framework for lifecycle, configuration, and communication abstraction.

## Architecture Diagram

```
┌────────────────────────────────────┐
│ Agent                              │
│                                    │
│  ┌─────────────┐    ┌────────────┐ │
│  │   Handlers  │    │  Lifecycle │ │
│  └─────────────┘    └────────────┘ │
│          │                │        │
│  ┌─────────────────────────────┐   │
│  │        Communicator         │   │
│  └─────────────────────────────┘   │
└────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│            Network/MCP              │
└─────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│ Other Agents/Services              │
└────────────────────────────────────┘
```

## Data Flow

1. An agent receives a message through its communicator
2. The communicator passes the message to the appropriate handler
3. The handler processes the message and returns a response
4. The communicator sends the response back to the sender

## Configuration

OpenMAS uses a configuration system for both agents and communicators, making it easy to set up and customize behavior.
