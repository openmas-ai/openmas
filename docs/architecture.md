# OpenMAS Architecture

This document provides an overview of the OpenMAS architecture.

## Core Components

### Agent

The `Agent` class is the central component in OpenMAS. It provides:

- Message handling
- Communication management
- Lifecycle management

### Communicator

Communicators handle the message transport between agents and services. OpenMAS provides:

- `HTTPCommunicator` for HTTP-based communication
- `MCPCommunicator` for high-performance in-memory communication

### Handlers

Handlers are functions registered with an agent to process specific message types.

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
