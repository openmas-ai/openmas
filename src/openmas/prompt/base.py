"""Core prompt management for OpenMAS.

This module provides a flexible and extensible prompt management system for OpenMAS,
enabling agents to organize, version, and reuse prompts across different contexts.
"""

import datetime
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class PromptConfig(BaseModel):
    """Developer-facing configuration for a prompt (for YAML/project config)."""

    name: str = Field(..., description="Name of the prompt")
    template: Optional[str] = Field(None, description="Prompt template string (inline)")
    template_file: Optional[str] = Field(None, description="Path to template file (relative to prompts_dir)")
    input_variables: List[str] = Field(default_factory=list, description="Variables required by the template")


class PromptMetadata(BaseModel):
    """Metadata for a prompt."""

    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    tags: Set[str] = Field(default_factory=set)
    author: Optional[str] = None
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class PromptContent(BaseModel):
    """Content for a prompt."""

    system: Optional[str] = None
    template: Optional[str] = None
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    context_keys: Set[str] = Field(default_factory=set)
    fallback: Optional[str] = None


class Prompt(BaseModel):
    """A prompt definition with metadata and content."""

    metadata: PromptMetadata
    content: PromptContent
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def get_system_prompt(self) -> Optional[str]:
        """Get the system prompt."""
        return self.content.system

    def get_template(self) -> Optional[str]:
        """Get the template for this prompt."""
        return self.content.template

    def get_examples(self) -> List[Dict[str, Any]]:
        """Get examples for this prompt."""
        return self.content.examples

    def to_dict(self) -> Dict[str, Any]:
        """Convert the prompt to a dictionary."""
        data = self.model_dump()

        # Convert sets to lists for JSON serialization
        if "metadata" in data and "tags" in data["metadata"]:
            data["metadata"]["tags"] = list(data["metadata"]["tags"])

        if "content" in data and "context_keys" in data["content"]:
            data["content"]["context_keys"] = list(data["content"]["context_keys"])

        return data

    def to_json(self, pretty: bool = False) -> str:
        """Convert the prompt to JSON."""
        if pretty:
            return json.dumps(self.to_dict(), indent=2)
        return json.dumps(self.to_dict())


class PromptStorage(BaseModel):
    """Base class for prompt storage backends."""

    async def save(self, prompt: Prompt) -> None:
        """Save a prompt to storage.

        Args:
            prompt: The prompt to save.
        """
        raise NotImplementedError("Subclasses must implement save")

    async def load(self, prompt_id: str) -> Optional[Prompt]:
        """Load a prompt from storage.

        Args:
            prompt_id: The ID of the prompt to load.

        Returns:
            The loaded prompt, or None if not found.
        """
        raise NotImplementedError("Subclasses must implement load")

    async def list(self, tag: Optional[str] = None) -> List[PromptMetadata]:
        """List available prompts.

        Args:
            tag: Optional tag to filter by.

        Returns:
            List of prompt metadata for available prompts.
        """
        raise NotImplementedError("Subclasses must implement list")

    async def delete(self, prompt_id: str) -> bool:
        """Delete a prompt.

        Args:
            prompt_id: The ID of the prompt to delete.

        Returns:
            True if the prompt was deleted, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement delete")


class FileSystemPromptStorage(PromptStorage):
    """Store prompts in the file system."""

    path: Path = Field(..., description="Path to store prompts")

    def __init__(self, **data: Any) -> None:
        """Initialize the storage with a path."""
        super().__init__(**data)
        self.path.mkdir(parents=True, exist_ok=True)

    async def save(self, prompt: Prompt) -> None:
        """Save a prompt to the file system."""
        file_path = self.path / f"{prompt.id}.json"
        with open(file_path, "w") as f:
            f.write(prompt.to_json(pretty=True))

    async def load(self, prompt_id: str) -> Optional[Prompt]:
        """Load a prompt from the file system."""
        file_path = self.path / f"{prompt_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, "r") as f:
            data = json.load(f)
            return Prompt(**data)

    async def list(self, tag: Optional[str] = None) -> List[PromptMetadata]:
        """List available prompts in the file system."""
        result: List[PromptMetadata] = []
        for file_path in self.path.glob("*.json"):
            with open(file_path, "r") as f:
                data = json.load(f)
                metadata = PromptMetadata(**data.get("metadata", {}))
                if tag is None or tag in metadata.tags:
                    result.append(metadata)
        return result

    async def delete(self, prompt_id: str) -> bool:
        """Delete a prompt from the file system."""
        file_path = self.path / f"{prompt_id}.json"
        if not file_path.exists():
            return False

        file_path.unlink()
        return True


class MemoryPromptStorage(PromptStorage):
    """Store prompts in memory."""

    prompts: Dict[str, Prompt] = Field(default_factory=dict)

    async def save(self, prompt: Prompt) -> None:
        """Save a prompt to memory."""
        self.prompts[prompt.id] = prompt

    async def load(self, prompt_id: str) -> Optional[Prompt]:
        """Load a prompt from memory."""
        return self.prompts.get(prompt_id)

    async def list(self, tag: Optional[str] = None) -> List[PromptMetadata]:
        """List available prompts in memory."""
        if tag is None:
            return [p.metadata for p in self.prompts.values()]
        return [p.metadata for p in self.prompts.values() if tag in p.metadata.tags]

    async def delete(self, prompt_id: str) -> bool:
        """Delete a prompt from memory."""
        if prompt_id not in self.prompts:
            return False

        del self.prompts[prompt_id]
        return True


class PromptManager:
    """Manages prompts for an agent."""

    def __init__(self, storage: Optional[PromptStorage] = None, prompts_base_path: Optional[Path] = None) -> None:
        """Initialize the prompt manager.

        Args:
            storage: Optional storage backend for prompts.
            prompts_base_path: Optional base path for resolving template_file in PromptConfig.
        """
        self.storage = storage or MemoryPromptStorage()
        self._prompts: Dict[str, Prompt] = {}
        self.prompts_base_path = prompts_base_path

    def load_prompts_from_config(self, prompt_configs: List[PromptConfig]) -> List[Prompt]:
        """Load prompts from a list of PromptConfig objects, resolving template_file if needed."""
        loaded_prompts = []
        for config in prompt_configs:
            # Determine template content
            template = config.template
            if config.template_file:
                if not self.prompts_base_path:
                    raise ValueError("prompts_base_path must be set to resolve template_file")
                template_path = self.prompts_base_path / config.template_file
                if not template_path.exists():
                    raise FileNotFoundError(f"Prompt template file not found: {template_path}")
                template = template_path.read_text(encoding="utf-8")
            # Build Prompt object
            metadata = PromptMetadata(name=config.name)
            content = PromptContent(template=template)
            prompt = Prompt(metadata=metadata, content=content)
            self._prompts[config.name] = prompt
            loaded_prompts.append(prompt)
        return loaded_prompts

    async def create_prompt(
        self,
        name: str,
        description: Optional[str] = None,
        system: Optional[str] = None,
        template: Optional[str] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[Set[str]] = None,
        author: Optional[str] = None,
    ) -> Prompt:
        """Create a new prompt.

        Args:
            name: Name of the prompt
            description: Optional description
            system: Optional system prompt
            template: Optional template
            examples: Optional examples for few-shot learning
            tags: Optional tags for categorizing prompts
            author: Optional author name

        Returns:
            The created prompt
        """
        metadata = PromptMetadata(
            name=name,
            description=description,
            tags=tags or set(),
            author=author,
        )

        content = PromptContent(
            system=system,
            template=template,
            examples=examples or [],
        )

        prompt = Prompt(metadata=metadata, content=content)

        # Save to local cache
        self._prompts[prompt.id] = prompt

        # Save to storage if available
        if self.storage:
            await self.storage.save(prompt)

        return prompt

    async def get_prompt(self, prompt_id: str) -> Optional[Prompt]:
        """Get a prompt by ID.

        Args:
            prompt_id: The ID of the prompt to get.

        Returns:
            The prompt, or None if not found.
        """
        # Check local cache first
        if prompt_id in self._prompts:
            return self._prompts[prompt_id]

        # Check storage
        if self.storage:
            prompt = await self.storage.load(prompt_id)
            if prompt:
                # Update local cache
                self._prompts[prompt_id] = prompt
                return prompt

        return None

    async def get_prompt_by_name(self, name: str) -> Optional[Prompt]:
        """Get a prompt by name.

        Args:
            name: The name of the prompt to get

        Returns:
            The prompt with the given name, or None if not found
        """
        # Check local cache first
        for prompt in self._prompts.values():
            if prompt.metadata.name == name:
                return prompt

        # Check storage
        all_prompts = await self.storage.list()
        for metadata in all_prompts:
            if metadata.name == name:
                prompt_id = metadata.id
                loaded_prompt = await self.storage.load(prompt_id)
                if loaded_prompt is not None:
                    # Update local cache
                    self._prompts[loaded_prompt.id] = loaded_prompt
                    return loaded_prompt

        return None

    async def update_prompt(self, prompt_id: str, **kwargs: Any) -> Optional[Prompt]:
        """Update a prompt.

        Args:
            prompt_id: The ID of the prompt to update.
            **kwargs: Fields to update.

        Returns:
            The updated prompt, or None if not found.
        """
        prompt = await self.get_prompt(prompt_id)
        if not prompt:
            return None

        # Update metadata fields
        metadata_fields = ["name", "description", "version", "tags", "author"]
        metadata_updates = {}
        for field in metadata_fields:
            if field in kwargs:
                metadata_updates[field] = kwargs[field]

        if metadata_updates:
            prompt.metadata = PromptMetadata(**{**prompt.metadata.model_dump(), **metadata_updates})
            prompt.metadata.updated_at = datetime.datetime.now().isoformat()

        # Update content fields
        content_fields = ["system", "template", "examples", "context_keys", "fallback"]
        content_updates = {}
        for field in content_fields:
            if field in kwargs:
                content_updates[field] = kwargs[field]

        if content_updates:
            prompt.content = PromptContent(**{**prompt.content.model_dump(), **content_updates})

        # Save updates
        self._prompts[prompt_id] = prompt
        if self.storage:
            await self.storage.save(prompt)

        return prompt

    async def delete_prompt(self, prompt_id: str) -> bool:
        """Delete a prompt.

        Args:
            prompt_id: The ID of the prompt to delete.

        Returns:
            True if the prompt was deleted, False otherwise.
        """
        # Remove from local cache
        if prompt_id in self._prompts:
            del self._prompts[prompt_id]

        # Remove from storage
        if self.storage:
            return await self.storage.delete(prompt_id)

        return True

    async def list_prompts(self, tag: Optional[str] = None) -> List[PromptMetadata]:
        """List available prompts.

        Args:
            tag: Optional tag to filter by.

        Returns:
            List of prompt metadata.
        """
        if self.storage:
            return await self.storage.list(tag)

        # Use local cache if no storage
        if tag is None:
            return [p.metadata for p in self._prompts.values()]
        return [p.metadata for p in self._prompts.values() if tag in p.metadata.tags]

    async def render_prompt(
        self,
        prompt_id: str,
        context: Optional[Dict[str, Any]] = None,
        system_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Render a prompt with context.

        Args:
            prompt_id: The ID of the prompt to render.
            context: Optional context to use for rendering.
            system_override: Optional system prompt override.

        Returns:
            The rendered prompt as a dictionary with system and content fields,
            or None if the prompt was not found.
        """
        prompt = await self.get_prompt(prompt_id)
        if not prompt:
            return None

        context = context or {}

        # Handle system prompt
        system = system_override or prompt.content.system

        # Handle template
        content = prompt.content.template
        if content and context:
            # Simple template rendering (in a real implementation, use a proper template engine)
            for key, value in context.items():
                if isinstance(value, (str, int, float, bool)):
                    placeholder = f"{{{{{key}}}}}"
                    content = content.replace(placeholder, str(value))

        # Return rendered prompt
        result = {"system": system, "content": content}

        return result
