# Use Case: Chesspal.ai Refactoring

This document outlines the target architecture for refactoring the `chesspal.ai` application into a Multi-Agent System (MAS) using OpenMAS. This use case served as a primary driver for early versions of the framework, particularly highlighting the need for robust Model Context Protocol (MCP) integration.

*(Based on Appendix B of the OpenMAS Design Document v0.2.3)*

## Background

`chesspal.ai` involves detecting chess board states from images, managing game logic, interacting with a chess engine (Stockfish), and generating commentary. Refactoring this into an MAS aims to improve modularity, scalability, and maintainability.

## Target MAS Architecture

The proposed MAS consists of the following agents, primarily communicating via MCP:

### 1. Orchestrator Agent

* **Role:** Central coordinator of the system. Manages the overall game flow, maintains the current game state, and orchestrates interactions between other agents and potentially a user interface (GUI).
* **Key Responsibilities:**
    * Game state management (e.g., current board position, move history, whose turn).
    * Persisting game state (e.g., using SQLite for development, PostgreSQL for production).
    * Handling input (e.g., moves submitted from a GUI, requests for game state).
    * Delegating tasks to other agents (requesting commentary, requesting move analysis).
    * Receiving results from other agents and updating the game state.
* **Communication (MCP):**
    * **MCP Server:** Runs an MCP Server (using `McpServerAgent` or `McpSseCommunicator` in server mode) to expose an interface for external clients (like a GUI) to connect. This interface would allow clients to:
        * Get the current game state (e.g., via an MCP Resource or Tool).
        * Submit player moves (e.g., via an MCP Tool call).
        * Receive game updates (potentially via streaming or notifications).
    * **MCP Client:** Acts as an MCP Client (using `BaseAgent` with `McpSseCommunicator` or `McpStdioCommunicator` in client mode) to interact with the Commentary and Stockfish agents. It would use `send_request` mapped to MCP actions like:
        * `call_tool` on the Commentary Agent to generate commentary for a move.
        * `call_tool` on the Stockfish Agent to get move analysis or the best move.
* **Dependencies & OpenMAS Requirements:**
    * Robust OpenMAS wrappers for MCP server (`FastMCP`) and client (`ClientSession`) functionality via the official `mcp` SDK (v1.6+).
    * `BaseAgent` must support standard `asyncio` patterns for database interactions (e.g., using `asyncpg` or `aiosqlite`).
    * Easy configuration of service URLs to connect to the other agents.

### 2. Commentary Agent

* **Role:** Generates natural language commentary about the chess game state or recent moves.
* **Key Responsibilities:**
    * Receiving requests from the Orchestrator containing game context (e.g., current FEN, last move).
    * Interacting with a Large Language Model (LLM), such as Google's Gemma or Anthropic's Claude, to generate commentary text based on the provided context.
    * Returning the generated commentary to the Orchestrator.
* **Communication (MCP):**
    * **MCP Server:** Runs an MCP Server (using `McpServerAgent` or similar). It exposes its functionality, likely as an MCP Tool (e.g., `generate_commentary`) that the Orchestrator can call via `send_request` (mapping to `call_tool`). The tool would accept game context as input and return the commentary string.
* **Dependencies & OpenMAS Requirements:**
    * OpenMAS MCP server capabilities (`McpServerAgent` or `McpSseCommunicator`/`McpStdioCommunicator` in server mode).
    * Compatibility with LLM integration libraries (e.g., `google-generativeai`, `anthropic`) within the `BaseAgent`'s async environment. See [LLM Integration Guide](../guides/llm_integration.md).
    * Ability to load LLM API keys and model names via the OpenMAS configuration system.

### 3. Stockfish Agent

* **Role:** Provides chess engine capabilities using the Stockfish engine. Performs move validation, calculates the best move, and provides board analysis.
* **Key Responsibilities:**
    * Managing an underlying Stockfish engine process.
    * Receiving requests from the Orchestrator (e.g., "validate move", "get best move for FEN", "analyze position").
    * Interacting with the Stockfish process (likely via UCI protocol).
    * Returning the results (e.g., best move in UCI notation, evaluation score) to the Orchestrator.
* **Communication (MCP):**
    * **MCP Server:** Runs an MCP Server (using `McpServerAgent` or similar). It exposes its functionality as one or more MCP Tools (e.g., `get_best_move`, `validate_move`, `analyze_position`) that the Orchestrator can call.
* **Dependencies & OpenMAS Requirements:**
    * OpenMAS MCP server capabilities.
    * `BaseAgent` must support managing external subprocesses asynchronously (e.g., using `asyncio.create_subprocess_exec` to run and communicate with Stockfish).
    * Ability to configure the path to the Stockfish executable.

## Summary of Framework Requirements Derived

This use case highlights the need for OpenMAS to provide:

1.  **Robust MCP Integration:** Stable, easy-to-use, and correct wrappers/abstractions around the official `mcp` Python SDK (v1.6+) for both client (`ClientSession` via `send_request`) and server (`FastMCP` via `McpServerAgent` or communicators in server mode) roles.
2.  **Async Compatibility:** The `BaseAgent` structure must seamlessly support standard asynchronous operations required by the agents, including database access, external API calls (LLMs), and managing subprocesses, without blocking the event loop.
3.  **Configuration:** Flexible configuration system to manage agent names, communication settings (ports, types), service URLs for inter-agent communication, API keys, and external tool paths.
4.  **Integration:** Facilitate the integration of external libraries/SDKs (LLM clients, DB drivers, subprocess management) within the agent's lifecycle methods (`setup`, `run`).
