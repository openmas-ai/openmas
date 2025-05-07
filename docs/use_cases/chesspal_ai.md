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
* **Enhanced Implementation with Prompt Management:**
    * Uses `PromptMcpAgent` to maintain a library of commentary prompts for different game scenarios
    * Leverages template rendering to insert game state into prompts
    * Uses the sampling system to control output parameters like temperature and length

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

## Extended Architecture with Prompt Management and Sampling

The ChessPal use case can be significantly enhanced with OpenMAS's new prompt management and sampling capabilities. This section outlines how these features can be integrated into the system.

### Commentary Agent with Prompt Management

The Commentary Agent can be refactored to leverage the `PromptMcpAgent` class, which provides built-in prompt management and sampling capabilities:

```python
from openmas.agent import PromptMcpAgent
from typing import Dict, Any, Optional

class ChessCommentaryAgent(PromptMcpAgent):
    """Chess commentary agent that provides natural language commentary on chess games."""

    async def setup(self):
        """Set up the agent with prompts and communication."""
        await super().setup()

        # Initialize prompt library with different commentary styles and purposes
        self.prompts = {}

        # Basic move commentary
        self.prompts["move_commentary"] = await self.create_prompt(
            name="move_commentary",
            description="Provides commentary for a chess move",
            system="You are an enthusiastic chess commentator who explains moves clearly.",
            template=(
                "Current board position (FEN notation): {{fen}}\n"
                "Last move played: {{last_move}}\n"
                "Player who moved: {{player}}\n\n"
                "Provide engaging commentary about this move in 2-3 sentences."
            ),
            tags={"chess", "commentary", "moves"}
        )

        # Game situation analysis
        self.prompts["game_analysis"] = await self.create_prompt(
            name="game_analysis",
            description="Analyzes the current game situation",
            system="You are a chess grandmaster providing insightful analysis.",
            template=(
                "Current board position (FEN notation): {{fen}}\n"
                "Move history: {{move_history}}\n"
                "Current player to move: {{player_to_move}}\n\n"
                "Analyze the current game situation. Comment on piece development, "
                "board control, and potential strategies for both players."
            ),
            tags={"chess", "analysis", "strategy"}
        )

        # Opening identification
        self.prompts["opening_commentary"] = await self.create_prompt(
            name="opening_commentary",
            description="Identifies and comments on chess openings",
            system="You are a chess opening expert who can identify openings from move sequences.",
            template=(
                "Current move sequence: {{move_sequence}}\n\n"
                "Identify the chess opening being played, if recognizable. "
                "Explain the key ideas behind this opening and potential variations."
            ),
            tags={"chess", "commentary", "openings"}
        )

        # Beginner-friendly commentary
        self.prompts["beginner_commentary"] = await self.create_prompt(
            name="beginner_commentary",
            description="Chess commentary tailored for beginners",
            system=(
                "You are a patient chess teacher who explains concepts in simple terms. "
                "Avoid using advanced terminology without explanation. Focus on basic "
                "principles and learning opportunities."
            ),
            template=(
                "Current board position (FEN notation): {{fen}}\n"
                "Last move played: {{last_move}}\n"
                "Player level: Beginner\n\n"
                "Explain this chess position and the last move in terms a beginner can understand. "
                "Highlight any basic principles that apply and learning opportunities."
            ),
            tags={"chess", "commentary", "beginner"}
        )

        # Register prompts with MCP server (if running in server mode)
        if self._server_mode:
            await self.register_prompts_with_server()

        # Set up tool handlers
        self.add_tool_handler("generate_commentary", self.handle_commentary_request)
        self.add_tool_handler("analyze_position", self.handle_analysis_request)
        self.add_tool_handler("identify_opening", self.handle_opening_request)

    async def handle_commentary_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request for move commentary."""
        fen = payload.get("fen", "")
        last_move = payload.get("last_move", "")
        player = payload.get("player", "")
        style = payload.get("style", "standard")

        # Select the appropriate prompt based on style
        prompt_id = self.prompts["move_commentary"].id
        if style == "beginner":
            prompt_id = self.prompts["beginner_commentary"].id

        # Sample from the selected prompt
        result = await self.sample(
            prompt_id=prompt_id,
            context={
                "fen": fen,
                "last_move": last_move,
                "player": player
            },
            parameters={
                "temperature": 0.7,
                "max_tokens": 200
            }
        )

        return {"commentary": result.content}

    async def handle_analysis_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request for game analysis."""
        fen = payload.get("fen", "")
        move_history = payload.get("move_history", "")
        player_to_move = payload.get("player_to_move", "")

        result = await self.sample(
            prompt_id=self.prompts["game_analysis"].id,
            context={
                "fen": fen,
                "move_history": move_history,
                "player_to_move": player_to_move
            },
            parameters={
                "temperature": 0.3,  # Lower temperature for more focused analysis
                "max_tokens": 500
            }
        )

        return {"analysis": result.content}

    async def handle_opening_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request to identify a chess opening."""
        move_sequence = payload.get("move_sequence", "")

        result = await self.sample(
            prompt_id=self.prompts["opening_commentary"].id,
            context={
                "move_sequence": move_sequence
            },
            parameters={
                "temperature": 0.2,  # Low temperature for factual accuracy
                "max_tokens": 300
            }
        )

        return {"opening_analysis": result.content}
```

Key benefits of this implementation:

1. **Structured Prompt Management**: Different prompts for different commentary needs (move commentary, analysis, opening identification)
2. **Dynamic Templating**: Game state is inserted into prompts via template variables
3. **Parameter Control**: Control over sampling parameters like temperature and max_tokens
4. **MCP Integration**: Prompts can be registered as MCP resources automatically
5. **Versioning & Metadata**: Prompts include version information, tags, and metadata
6. **Extensibility**: Easy to add new commentary styles or specialized prompts

### Orchestrator Agent with Sampling Interface

The Orchestrator Agent can leverage the sampling interface to generate personalized responses for players:

```python
from openmas.agent import PromptMcpAgent
from typing import Dict, Any, Optional

class ChessOrchestratorAgent(PromptMcpAgent):
    """Orchestrator agent that manages the chess game and coordinates other agents."""

    async def setup(self):
        """Set up the agent."""
        await super().setup()

        # Initialize player interaction prompts
        self.prompts = {}

        # Welcome message prompt
        self.prompts["welcome"] = await self.create_prompt(
            name="welcome_message",
            description="Generates a welcome message for players",
            system="You are ChessPal, a friendly chess assistant.",
            template=(
                "Player name: {{player_name}}\n"
                "Player rating: {{player_rating}}\n"
                "Time of day: {{time_of_day}}\n\n"
                "Generate a friendly, personalized welcome message for this chess player."
            ),
            tags={"interaction", "welcome"}
        )

        # Game advice prompt
        self.prompts["advice"] = await self.create_prompt(
            name="game_advice",
            description="Provides personalized advice for a player during a game",
            system="You are ChessPal, a helpful chess coach.",
            template=(
                "Player name: {{player_name}}\n"
                "Player rating: {{player_rating}}\n"
                "Current position (FEN): {{fen}}\n"
                "Player color: {{player_color}}\n"
                "Move history: {{move_history}}\n\n"
                "Provide brief, helpful advice for this player based on the current game situation."
            ),
            tags={"interaction", "advice"}
        )

        # Initialize communicators to other agents
        # ... (code to set up communication with other agents)

    async def generate_welcome_message(self, player_name: str, player_rating: int) -> str:
        """Generate a personalized welcome message for a player."""
        # Get the current time of day
        import datetime
        hour = datetime.datetime.now().hour
        time_of_day = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 18 else "evening"

        # Sample from the welcome prompt
        result = await self.sample(
            prompt_id=self.prompts["welcome"].id,
            context={
                "player_name": player_name,
                "player_rating": player_rating,
                "time_of_day": time_of_day
            },
            parameters={
                "temperature": 0.8,  # Higher temperature for more varied, creative messages
                "max_tokens": 100
            }
        )

        return result.content

    async def generate_advice(self, player_name: str, player_rating: int,
                             fen: str, player_color: str, move_history: str) -> str:
        """Generate personalized advice for a player during a game."""
        result = await self.sample(
            prompt_id=self.prompts["advice"].id,
            context={
                "player_name": player_name,
                "player_rating": player_rating,
                "fen": fen,
                "player_color": player_color,
                "move_history": move_history
            },
            parameters={
                "temperature": 0.5,
                "max_tokens": 150
            }
        )

        return result.content

    async def handle_player_move(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a move submitted by a player."""
        # ... (code to validate and process the move)

        # Get commentary from the commentary agent
        commentary_result = await self.send_request(
            target="commentary_agent",
            action="call_tool",
            tool_name="generate_commentary",
            arguments={
                "fen": current_fen,
                "last_move": move,
                "player": player_name,
                "style": "standard"  # or "beginner" based on player preference
            }
        )

        # ... (code to update game state)

        return {
            "success": True,
            "commentary": commentary_result.get("commentary", ""),
            "board_state": current_fen,
            # ... other response fields
        }
```

## Summary of Framework Requirements Derived

This use case highlights the need for OpenMAS to provide:

1.  **Robust MCP Integration:** Stable, easy-to-use, and correct wrappers/abstractions around the official `mcp` Python SDK (v1.6+) for both client (`ClientSession` via `send_request`) and server (`FastMCP` via `McpServerAgent` or communicators in server mode) roles.
2.  **Async Compatibility:** The `BaseAgent` structure must seamlessly support standard asynchronous operations required by the agents, including database access, external API calls (LLMs), and managing subprocesses, without blocking the event loop.
3.  **Configuration:** Flexible configuration system to manage agent names, communication settings (ports, types), service URLs for inter-agent communication, API keys, and external tool paths.
4.  **Integration:** Facilitate the integration of external libraries/SDKs (LLM clients, DB drivers, subprocess management) within the agent's lifecycle methods (`setup`, `run`).
5.  **Prompt Management:** Structured system for organizing, versioning, and retrieving prompts for different purposes within agents.
6.  **Sampling Interface:** Consistent interface for interacting with language models across different providers, with control over parameters.
7.  **MCP Prompt Integration:** Ability to expose prompts as MCP resources that can be accessed by other agents.

## Benefits of Prompt Management for ChessPal

The integration of prompt management and sampling features provides several key benefits for the ChessPal system:

1. **Improved Modularity:** Prompts are separated from code, making them easier to manage and update
2. **Versioning and Tracking:** Changes to prompt content can be tracked and versioned
3. **Personalization:** Templates allow for dynamic insertion of game state and player information
4. **Parameter Tuning:** Fine control over sampling parameters for different use cases
5. **MCP Integration:** Prompts can be exposed as MCP resources for consumption by other agents
6. **Role-Specific Content:** Different prompts for different roles (commentator, coach, analyst)
7. **Consistent Interface:** Standard interface regardless of the underlying LLM provider

This approach demonstrates how OpenMAS's prompt management and sampling features enable more sophisticated agent behaviors while maintaining clean separation of concerns and modular design.
