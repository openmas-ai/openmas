# Prompt Management and Sampling

This guide introduces OpenMAS's prompt management and sampling capabilities, which enable agents to organize, version, reuse prompts, and interact with language models in a standardized way.

## Introduction

The prompt management and sampling system in OpenMAS provides:

- A structured way to define, store, and retrieve prompts
- Version control and metadata for prompts
- Template rendering with context variables
- A sampling abstraction for consistent interaction with language models
- Integration with MCP (Model Context Protocol)

These features are particularly useful for building agents that need to:

- Maintain a library of prompts for different contexts and scenarios
- Sample from language models with consistent parameters
- Share prompts between agents or expose them via MCP

## Prompt Management

### Core Components

- **Prompt**: A complete prompt definition with metadata and content
- **PromptMetadata**: Information about a prompt (name, version, tags, etc.)
- **PromptContent**: The actual content of a prompt (system, template, examples)
- **PromptStorage**: Abstract storage backend for prompts
- **PromptManager**: Main interface for managing prompts

### Basic Usage

```python
from openmas.prompt import PromptManager, MemoryPromptStorage

# Create a prompt manager with in-memory storage
prompt_manager = PromptManager(storage=MemoryPromptStorage())

# Create a prompt
prompt = await prompt_manager.create_prompt(
    name="chess_analysis",
    description="Analyzes a chess position",
    system="You are a chess expert that analyzes positions thoroughly.",
    template="Analyze this chess position: {{position}}",
    tags={"chess", "analysis"},
    author="ChessPal Team"
)

# Retrieve a prompt by ID
retrieved_prompt = await prompt_manager.get_prompt(prompt.id)

# Render a prompt with context
rendered = await prompt_manager.render_prompt(
    prompt.id,
    context={"position": "e4 e5 Nf3 Nc6 Bb5"}
)

# Update a prompt
updated_prompt = await prompt_manager.update_prompt(
    prompt.id,
    system="You are a grandmaster-level chess coach providing insightful analysis.",
    template="Analyze this chess position and provide strategic advice: {{position}}"
)

# List all prompts
prompts = await prompt_manager.list_prompts()

# List prompts with a specific tag
chess_prompts = await prompt_manager.list_prompts(tag="chess")

# Delete a prompt
success = await prompt_manager.delete_prompt(prompt.id)
```

### Storage Options

OpenMAS provides multiple storage backends for prompts:

#### In-Memory Storage

```python
from openmas.prompt import PromptManager, MemoryPromptStorage

# Create an in-memory storage (useful for testing or simple applications)
storage = MemoryPromptStorage()
prompt_manager = PromptManager(storage=storage)
```

#### File System Storage

```python
from openmas.prompt import PromptManager, FileSystemPromptStorage
from pathlib import Path

# Create a file system storage (persists prompts as JSON files)
storage = FileSystemPromptStorage(path=Path("./prompts"))
prompt_manager = PromptManager(storage=storage)
```

## Sampling from Language Models

The sampling module provides a consistent way to interact with language models across different providers.

### Core Components

- **SamplingParameters**: Controls sampling behavior (temperature, max_tokens, etc.)
- **Message**: A message in a conversation (role and content)
- **SamplingContext**: Complete context for a sampling operation
- **SamplingResult**: Result of a sampling operation
- **Sampler**: Base class for samplers

### Basic Usage

```python
from openmas.sampling import SamplingParameters, MessageRole
from openmas.sampling.providers.mcp import McpSampler
from openmas.communication.mcp.sse_communicator import McpSseCommunicator

# Create a communicator
communicator = McpSseCommunicator(
    agent_name="sampler_agent",
    service_urls={"llm_service": "http://localhost:8080"},
    server_mode=False,
)

# Create a sampler
sampler = McpSampler(
    communicator=communicator,
    target_service="llm_service",
    default_model="claude-3-opus-20240229"
)

# Create a sampling context
context = sampler.create_context(
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "What is the capital of France?"}
    ],
    parameters={"temperature": 0.7, "max_tokens": 500}
)

# Sample from the language model
result = await sampler.sample(context)
print(result.content)
```

### Sampling from a Prompt

You can also sample directly from a prompt:

```python
from openmas.prompt import Prompt, PromptContent, PromptMetadata
from openmas.sampling.providers.mcp import McpSampler

# Create a prompt
metadata = PromptMetadata(name="chess_commentary")
content = PromptContent(
    system="You are a chess commentator providing engaging commentary.",
    template="Provide commentary for this chess move: {{move}}"
)
prompt = Prompt(metadata=metadata, content=content)

# Sample from the prompt
result = await sampler.sample_from_prompt(
    prompt=prompt,
    context_vars={"move": "e4"},
    parameters={"temperature": 0.8},
    model="claude-3-sonnet-20240229"
)

print(result.content)
```

## Integration with MCP

OpenMAS provides seamless integration between prompt management and MCP.

### Registering Prompts with MCP

```python
from openmas.prompt import PromptManager
from openmas.prompt.mcp import McpPromptManager
from openmas.agent.mcp import McpServerAgent

# Create a prompt manager
prompt_manager = PromptManager()

# Create some prompts
chess_analysis = await prompt_manager.create_prompt(
    name="chess_analysis",
    system="You are a chess expert.",
    template="Analyze this position: {{position}}",
)

chess_commentary = await prompt_manager.create_prompt(
    name="chess_commentary",
    system="You are a chess commentator.",
    template="Provide commentary for this move: {{move}}",
)

# Create an MCP prompt manager
mcp_prompt_manager = McpPromptManager(prompt_manager)

# Create an MCP server agent
server_agent = McpServerAgent(name="chess_server")
await server_agent.setup()

# Register prompts with the server
await mcp_prompt_manager.register_prompt_with_server(
    prompt_id=chess_analysis.id,
    server=server_agent.communicator
)

# Or register all prompts at once
registered_prompts = await mcp_prompt_manager.register_all_prompts_with_server(
    server=server_agent.communicator
)
```

## Enhanced MCP Agent with Prompt Management

OpenMAS provides an enhanced MCP agent with built-in prompt management and sampling capabilities:

```python
from openmas.agent import PromptMcpAgent

# Create an agent with prompt management and sampling
agent = PromptMcpAgent(
    name="chess_agent",
    llm_service="llm_service",
    default_model="claude-3-opus-20240229"
)

# Setup the agent
await agent.setup()

# Create prompts
analysis_prompt = await agent.create_prompt(
    name="analysis",
    system="You are a chess analyst.",
    template="Analyze this position: {{position}}"
)

# Sample from a prompt
analysis = await agent.sample(
    prompt_id=analysis_prompt.id,
    context={"position": "e4 e5 Nf3 Nc6"},
    parameters={"temperature": 0.7}
)

# Sample directly from text
response = await agent.sample_text(
    system="You are a helpful assistant.",
    prompt="What opening begins with e4 e5 Nf3 Nc6?",
)

# Use the chat interface
result = await agent.chat(
    system="You are a chess tutor.",
    messages=[
        {"role": "user", "content": "What's the best response to e4?"}
    ],
    parameters={"temperature": 0.8}
)
```

## Example: ChessPal AI Integration

Here's a complete example of using prompt management and sampling in a chess agent:

```python
import asyncio
from openmas.agent import PromptMcpAgent

class ChessPalAgent(PromptMcpAgent):
    """Chess assistant agent with prompt management and LLM capabilities."""

    async def setup(self):
        """Set up the agent with prompts and communication."""
        await super().setup()

        # Create a set of chess-related prompts
        self.prompts = {}

        # Analysis prompt
        self.prompts["analysis"] = await self.create_prompt(
            name="chess_analysis",
            description="Analyzes a chess position in detail",
            system="You are a chess analysis engine that evaluates positions objectively. "
                   "Provide clear, concise analysis focusing on material, position, and tactics.",
            template="Analyze this chess position (FEN notation): {{fen}}\n\n"
                    "Current player to move: {{player_to_move}}\n\n"
                    "Recent moves: {{recent_moves}}",
            tags={"chess", "analysis"}
        )

        # Commentary prompt
        self.prompts["commentary"] = await self.create_prompt(
            name="chess_commentary",
            description="Provides engaging commentary on chess moves",
            system="You are an engaging chess commentator like those at major tournaments. "
                   "Your commentary is insightful, slightly dramatic, and helps viewers "
                   "understand the significance of moves.",
            template="The position is: {{fen}}\n\n"
                    "The move just played was: {{last_move}}\n\n"
                    "Provide engaging commentary on this move.",
            tags={"chess", "commentary"}
        )

        # Teaching prompt
        self.prompts["teaching"] = await self.create_prompt(
            name="chess_teaching",
            description="Explains chess concepts in an educational way",
            system="You are a patient chess coach who explains concepts clearly to students. "
                   "You adapt your explanations to be appropriate for the student's rating.",
            template="Student rating: {{student_rating}}\n\n"
                    "Explain this chess concept: {{concept}}\n\n"
                    "If relevant, reference the current position: {{fen}}",
            tags={"chess", "teaching"}
        )

        # Register prompts with MCP if in server mode
        if self._server_mode:
            await self.register_prompts_with_server()

    async def analyze_position(self, fen, player_to_move, recent_moves):
        """Analyze a chess position using LLM."""
        return await self.sample(
            prompt_id=self.prompts["analysis"].id,
            context={
                "fen": fen,
                "player_to_move": player_to_move,
                "recent_moves": recent_moves
            },
            parameters={"temperature": 0.3, "max_tokens": 800}
        )

    async def provide_commentary(self, fen, last_move):
        """Provide commentary for a chess move."""
        return await self.sample(
            prompt_id=self.prompts["commentary"].id,
            context={
                "fen": fen,
                "last_move": last_move
            },
            parameters={"temperature": 0.7, "max_tokens": 300}
        )

    async def explain_concept(self, concept, student_rating, fen=None):
        """Explain a chess concept to a student."""
        return await self.sample(
            prompt_id=self.prompts["teaching"].id,
            context={
                "concept": concept,
                "student_rating": student_rating,
                "fen": fen or "Not applicable"
            },
            parameters={"temperature": 0.5, "max_tokens": 1000}
        )

# Example usage
async def main():
    agent = ChessPalAgent(
        name="chesspal",
        llm_service="claude",
        default_model="claude-3-sonnet-20240229"
    )
    await agent.setup()

    # Analyze a position
    analysis = await agent.analyze_position(
        fen="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        player_to_move="white",
        recent_moves="1. e4 e5 2. Nf3 Nc6"
    )
    print("Analysis:", analysis.content)

    # Provide commentary on a move
    commentary = await agent.provide_commentary(
        fen="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        last_move="Nc6"
    )
    print("Commentary:", commentary.content)

    # Explain a concept
    explanation = await agent.explain_concept(
        concept="The Italian Game opening",
        student_rating=1200
    )
    print("Explanation:", explanation.content)

if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

1. **Organize Prompts by Tags**: Use tags to categorize prompts by domain, purpose, or agent type.
2. **Version Control**: Update the version field when making significant changes to prompts.
3. **Storage Selection**: Choose the appropriate storage backend based on your needs:
   - `MemoryPromptStorage` for testing or simple applications
   - `FileSystemPromptStorage` for persistence between runs
4. **Template Design**: Keep templates focused and use variables consistently.
5. **Sampling Parameters**: Tune temperature, max_tokens, and other parameters based on the task:
   - Lower temperature (0.1-0.3) for factual, analytical tasks
   - Medium temperature (0.4-0.7) for balanced creativity and accuracy
   - Higher temperature (0.7-1.0) for creative, diverse outputs
6. **Error Handling**: Always handle potential errors in sampling operations.

## API Reference

For complete API documentation, see:
- [Prompt Management API Reference](/api_reference/#openmas.prompt)
- [Sampling API Reference](/api_reference/#openmas.sampling)
