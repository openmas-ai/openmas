# Prompt Management and Sampling Implementation Guide

This document provides detailed information about the implementation of OpenMAS's prompt management and sampling systems for contributors who want to understand, extend, or modify these modules.

## Architecture Overview

The prompt management and sampling systems are designed with the following principles:

- **Modularity**: Clear separation of concerns between different components
- **Extensibility**: Easy to extend with new storage backends, sampling providers, etc.
- **Type Safety**: Strong typing with Pydantic for all data models
- **Async-First**: All operations are async-compatible for integration with OpenMAS agents
- **Protocol Integration**: Seamless integration with MCP (Model Context Protocol)

The architecture consists of two primary subsystems:

1. **Prompt Management**: Defines, stores, and retrieves prompts
2. **Sampling**: Handles interaction with language models

### Directory Structure

```
src/openmas/
├── prompt/
│   ├── __init__.py
│   ├── base.py         # Core prompt management classes
│   └── mcp.py          # MCP integration
├── sampling/
│   ├── __init__.py
│   ├── base.py         # Core sampling abstractions
│   └── providers/      # Provider-specific implementations
│       ├── __init__.py
│       └── mcp.py      # MCP-specific sampler
└── agent/
    └── mcp_prompt.py   # Enhanced MCP agent with prompt & sampling
```

## Prompt Management System

### Core Classes

#### `PromptMetadata`

```python
class PromptMetadata(BaseModel):
    """Metadata for a prompt."""
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    tags: Set[str] = Field(default_factory=set)
    author: Optional[str] = None
```

Key design decisions:
- Uses ISO format for timestamps to ensure compatibility and ease of parsing
- Includes version field for tracking prompt evolution
- Tags are a set to prevent duplicates and enable efficient filtering

#### `PromptContent`

```python
class PromptContent(BaseModel):
    """Content for a prompt."""
    system: Optional[str] = None
    template: Optional[str] = None
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    context_keys: Set[str] = Field(default_factory=set)
    fallback: Optional[str] = None
```

Key design decisions:
- Separate system prompt and template for flexible composition
- Supports examples for few-shot learning
- `context_keys` tracks expected template variables (though not strictly enforced)
- `fallback` provides a default response if rendering fails

#### `Prompt`

```python
class Prompt(BaseModel):
    """A prompt definition with metadata and content."""
    metadata: PromptMetadata
    content: PromptContent
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
```

Key design decisions:
- Auto-generated UUID for stable identification across systems
- Separation of metadata and content for cleaner organization
- Helper methods for common operations like retrieving system prompt

#### `PromptStorage`

```python
class PromptStorage(BaseModel):
    """Base class for prompt storage backends."""
    async def save(self, prompt: Prompt) -> None: ...
    async def load(self, prompt_id: str) -> Optional[Prompt]: ...
    async def list(self, tag: Optional[str] = None) -> List[PromptMetadata]: ...
    async def delete(self, prompt_id: str) -> bool: ...
```

Key design decisions:
- Abstract base class to enable multiple storage implementations
- Async methods for compatibility with OpenMAS agents
- `list()` returns only metadata to reduce data transfer when listing many prompts

#### `PromptManager`

```python
class PromptManager:
    """Manages prompts for an agent."""
    def __init__(self, storage: Optional[PromptStorage] = None) -> None: ...
    async def create_prompt(self, name: str, ...) -> Prompt: ...
    async def get_prompt(self, prompt_id: str) -> Optional[Prompt]: ...
    async def get_prompt_by_name(self, name: str) -> Optional[Prompt]: ...
    async def update_prompt(self, prompt_id: str, **kwargs: Any) -> Optional[Prompt]: ...
    async def delete_prompt(self, prompt_id: str) -> bool: ...
    async def list_prompts(self, tag: Optional[str] = None) -> List[PromptMetadata]: ...
    async def render_prompt(self, prompt_id: str, ...) -> Optional[Dict[str, Any]]: ...
```

Key design decisions:
- Local caching of prompts for performance
- Defaults to `MemoryPromptStorage` if no storage provided
- Comprehensive CRUD operations
- Flexible prompt creation with optional parameters
- Simple template rendering (could be extended with a template engine)

### Storage Implementations

#### `MemoryPromptStorage`

In-memory storage suitable for testing or simple applications.

```python
class MemoryPromptStorage(PromptStorage):
    """Store prompts in memory."""
    prompts: Dict[str, Prompt] = Field(default_factory=dict)
```

#### `FileSystemPromptStorage`

File-based storage for persistence between runs.

```python
class FileSystemPromptStorage(PromptStorage):
    """Store prompts in the file system."""
    path: Path = Field(..., description="Path to store prompts")
```

Key design decisions:
- Each prompt is stored as a separate JSON file
- Files are named with the prompt's UUID
- Automatically creates storage directory if it doesn't exist

## Sampling System

### Core Classes

#### `SamplingParameters`

```python
class SamplingParameters(BaseModel):
    """Parameters for sampling from a language model."""
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=1024, gt=0)
    top_p: Optional[float] = Field(default=0.9, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=None, gt=0)
    stop_sequences: Optional[List[str]] = None
    repetition_penalty: Optional[float] = Field(default=None, ge=0.0)
    presence_penalty: Optional[float] = Field(default=None, ge=0.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=0.0)
    seed: Optional[int] = None
```

Key design decisions:
- Includes all common sampling parameters used by major LLM providers
- Uses Pydantic validators (ge, le, gt) to ensure valid parameter ranges
- All parameters are optional with sensible defaults
- `to_dict()` method omits None values for clean API calls

#### `MessageRole` and `Message`

```python
class MessageRole(str, Enum):
    """Role of a message in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class Message(BaseModel):
    """A message in a conversation."""
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = None
```

Key design decisions:
- Uses an Enum for roles to ensure consistent values
- Supports metadata for additional message information
- Simple structure aligns with common LLM provider APIs

#### `SamplingContext`

```python
class SamplingContext(BaseModel):
    """Context for a sampling operation."""
    system_prompt: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    parameters: SamplingParameters = Field(default_factory=SamplingParameters)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

Key design decisions:
- Complete context for a sampling operation
- Follows common patterns used by major LLM providers
- Factory method `from_prompt()` to create context from a prompt
- Helper methods for common operations

#### `SamplingResult`

```python
class SamplingResult(BaseModel):
    """Result of a sampling operation."""
    content: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_response: Optional[Any] = None
```

Key design decisions:
- Stores the essential response content plus additional metadata
- Captures raw response for debugging or advanced usage
- Includes common fields like usage stats and finish reason
- Serialization methods for consistent output

#### `Sampler` Protocol and Base Class

```python
@runtime_checkable
class SamplerProtocol(Protocol):
    """Protocol for samplers."""
    async def sample(self, context: SamplingContext, model: Optional[str] = None) -> SamplingResult: ...

class Sampler:
    """Base class for samplers."""
    async def sample(self, context: SamplingContext, model: Optional[str] = None) -> SamplingResult: ...
    @classmethod
    def create_context(cls, system: Optional[str] = None, ...) -> SamplingContext: ...
    async def sample_from_prompt(self, prompt: Prompt, ...) -> SamplingResult: ...
```

Key design decisions:
- Uses Protocol for structural typing
- Base class with shared functionality
- Helper methods for creating contexts and sampling from prompts
- Abstract `sample()` method to be implemented by subclasses

### Provider Implementations

#### `McpSampler`

```python
class McpSampler(Sampler):
    """Sampler that uses MCP to sample from a language model."""
    def __init__(self, communicator: BaseCommunicator, target_service: str, default_model: Optional[str] = None) -> None: ...
    async def sample(self, context: SamplingContext, model: Optional[str] = None) -> SamplingResult: ...
```

Key design decisions:
- Uses the existing MCP communicator infrastructure
- Validates that the communicator supports sampling
- Converts between OpenMAS sampling context and MCP format
- Handles error cases with appropriate exceptions

#### `McpAgentSampler`

```python
class McpAgentSampler(Sampler):
    """Sampler that uses an MCP agent to sample from a language model."""
    def __init__(self, agent: McpAgent, target_service: str, default_model: Optional[str] = None) -> None: ...
    async def sample(self, context: SamplingContext, model: Optional[str] = None) -> SamplingResult: ...
```

Key design decisions:
- Uses an MCP agent directly instead of a communicator
- Otherwise similar to `McpSampler`
- Allows more direct integration with agent functionality

## MCP Integration

### Prompt Registration with MCP

The `McpPromptManager` class handles registration of prompts with an MCP server:

```python
class McpPromptManager:
    """Manages prompts for MCP integration."""
    def __init__(self, prompt_manager: PromptManager) -> None: ...
    async def register_prompt_with_server(self, prompt_id: str, server: Any, name: Optional[str] = None) -> Optional[str]: ...
    async def register_all_prompts_with_server(self, server: Any, tag: Optional[str] = None) -> List[str]: ...
```

Key design decisions:
- Wraps a `PromptManager` to provide MCP-specific functionality
- Gracefully handles the case where MCP is not installed
- Creates handler functions that render prompts on demand
- Returns the registered names for verification

### Enhanced MCP Agent

The `PromptMcpAgent` class extends `McpAgent` with prompt management and sampling capabilities:

```python
class PromptMcpAgent(McpAgent):
    """Enhanced MCP agent with prompt management and sampling capabilities."""
    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None, prompt_manager: Optional[PromptManager] = None, **kwargs: Any) -> None: ...
    async def setup(self) -> None: ...
    async def register_prompts_with_server(self) -> None: ...
    async def create_prompt(self, name: str, ...) -> Prompt: ...
    async def render_prompt(self, prompt_id: str, ...) -> Optional[Dict[str, Any]]: ...
    async def sample(self, prompt_id: str, ...) -> SamplingResult: ...
    async def sample_text(self, system: Optional[str] = None, prompt: str = "", ...) -> str: ...
    async def chat(self, system: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None, ...) -> SamplingResult: ...
```

Key design decisions:
- Integrates all components (prompt management, sampling, MCP)
- Creates the sampler during setup based on provided configuration
- Provides high-level methods for common operations
- Automatically registers prompts with the server in server mode
- Lazy initialization of the sampler to handle different usage patterns

## Testing Strategy

The prompt management and sampling systems are thoroughly tested with unit tests:

1. **Component Tests**: Each class and method is tested individually
2. **Integration Tests**: Components are tested working together
3. **Edge Cases**: Tests cover error conditions, edge cases, and boundary values

Example test files:
- `tests/unit/prompt/test_prompt_manager.py`: Tests for prompt management
- `tests/unit/sampling/test_sampling.py`: Tests for sampling abstractions
- `tests/unit/sampling/providers/test_mcp_sampler.py`: Tests for MCP samplers
- `tests/unit/prompt/test_mcp_prompt_manager.py`: Tests for MCP prompt integration
- `tests/unit/agent/test_prompt_mcp_agent.py`: Tests for the enhanced MCP agent

## Future Improvements

Potential areas for enhancement:

1. **Advanced Template Engine**: Replace the simple template rendering with a more powerful engine like Jinja2
2. **Additional Storage Backends**: Implement database or cloud storage options
3. **Provider-Specific Samplers**: Add samplers for direct integration with OpenAI, Anthropic, etc.
4. **Streaming Support**: Add streaming capabilities for incremental results
5. **Batch Sampling**: Support for batch operations to improve throughput
6. **Caching**: Add caching layer for sampling results
7. **Prompt Versioning**: Enhanced versioning with history tracking
8. **Prompt Sharing**: Mechanism for sharing prompts between agents

## Contributing Guidelines

When contributing to these modules, please follow these guidelines:

1. **Testing**: Add tests for all new functionality
2. **Type Hints**: Use proper type hints throughout
3. **Docstrings**: Update docstrings for all public methods
4. **Backwards Compatibility**: Maintain compatibility when extending functionality
5. **Error Handling**: Use appropriate error types and provide helpful messages
6. **Logging**: Add appropriate logging at DEBUG, INFO, WARNING, and ERROR levels
7. **Performance**: Consider performance implications, especially for operations that might be called frequently

## Common Pitfalls

1. **Template Variables**: The simple template engine only supports simple replacements; consider using a proper template engine for complex cases
2. **Concurrency**: Be aware of concurrency issues when multiple agents share a PromptManager
3. **Large Prompts**: Very large prompts might cause performance issues; consider chunking or streaming
4. **Error Propagation**: Ensure errors from the sampling operations are properly propagated and handled
