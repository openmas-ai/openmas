"""Unit tests for the PromptManager class."""

import os
import pytest
from pathlib import Path
import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from openmas.prompt import (
    Prompt,
    PromptContent,
    PromptManager,
    PromptMetadata,
    PromptStorage,
    FileSystemPromptStorage,
    MemoryPromptStorage,
)


class TestPromptMetadata:
    """Tests for the PromptMetadata class."""

    def test_initialization(self):
        """Test basic initialization of PromptMetadata."""
        metadata = PromptMetadata(name="test_prompt")
        assert metadata.name == "test_prompt"
        assert metadata.description is None
        assert metadata.version == "1.0.0"
        assert metadata.created_at is not None
        assert metadata.updated_at is not None
        assert metadata.tags == set()
        assert metadata.author is None

    def test_initialization_with_values(self):
        """Test initialization of PromptMetadata with custom values."""
        metadata = PromptMetadata(
            name="test_prompt",
            description="A test prompt",
            version="2.0.0",
            tags={"test", "example"},
            author="Test Author",
        )
        assert metadata.name == "test_prompt"
        assert metadata.description == "A test prompt"
        assert metadata.version == "2.0.0"
        assert metadata.tags == {"test", "example"}
        assert metadata.author == "Test Author"


class TestPromptContent:
    """Tests for the PromptContent class."""

    def test_initialization(self):
        """Test basic initialization of PromptContent."""
        content = PromptContent()
        assert content.system is None
        assert content.template is None
        assert content.examples == []
        assert content.context_keys == set()
        assert content.fallback is None

    def test_initialization_with_values(self):
        """Test initialization of PromptContent with custom values."""
        content = PromptContent(
            system="You are a helpful assistant.",
            template="Answer the following question: {{question}}",
            examples=[
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "The capital of France is Paris."},
            ],
            context_keys={"question"},
            fallback="I don't know the answer to that question.",
        )
        assert content.system == "You are a helpful assistant."
        assert content.template == "Answer the following question: {{question}}"
        assert len(content.examples) == 2
        assert content.examples[0]["role"] == "user"
        assert content.context_keys == {"question"}
        assert content.fallback == "I don't know the answer to that question."


class TestPrompt:
    """Tests for the Prompt class."""

    def test_initialization(self):
        """Test basic initialization of Prompt."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent()
        prompt = Prompt(metadata=metadata, content=content)
        assert prompt.metadata == metadata
        assert prompt.content == content
        assert prompt.id is not None

    def test_get_system_prompt(self):
        """Test the get_system_prompt method."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(system="You are a helpful assistant.")
        prompt = Prompt(metadata=metadata, content=content)
        assert prompt.get_system_prompt() == "You are a helpful assistant."

    def test_get_template(self):
        """Test the get_template method."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(template="Answer the following question: {{question}}")
        prompt = Prompt(metadata=metadata, content=content)
        assert prompt.get_template() == "Answer the following question: {{question}}"

    def test_get_examples(self):
        """Test the get_examples method."""
        metadata = PromptMetadata(name="test_prompt")
        examples = [
            {"role": "user", "content": "What is the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."},
        ]
        content = PromptContent(examples=examples)
        prompt = Prompt(metadata=metadata, content=content)
        assert prompt.get_examples() == examples

    def test_to_dict(self):
        """Test the to_dict method."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(system="You are a helpful assistant.")
        prompt = Prompt(metadata=metadata, content=content)
        prompt_dict = prompt.to_dict()
        assert prompt_dict["metadata"]["name"] == "test_prompt"
        assert prompt_dict["content"]["system"] == "You are a helpful assistant."

    def test_to_json(self):
        """Test the to_json method."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(system="You are a helpful assistant.")
        prompt = Prompt(metadata=metadata, content=content)
        json_str = prompt.to_json()
        assert "test_prompt" in json_str
        assert "You are a helpful assistant" in json_str


class TestMemoryPromptStorage:
    """Tests for the MemoryPromptStorage class."""

    @pytest.fixture
    def storage(self):
        """Create a MemoryPromptStorage instance."""
        return MemoryPromptStorage()

    @pytest.fixture
    def prompt(self):
        """Create a sample prompt."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(system="You are a helpful assistant.")
        return Prompt(metadata=metadata, content=content)

    @pytest.mark.asyncio
    async def test_save_and_load(self, storage, prompt):
        """Test saving and loading a prompt."""
        await storage.save(prompt)
        loaded_prompt = await storage.load(prompt.id)
        assert loaded_prompt is not None
        assert loaded_prompt.id == prompt.id
        assert loaded_prompt.metadata.name == "test_prompt"
        assert loaded_prompt.content.system == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_list(self, storage, prompt):
        """Test listing prompts."""
        await storage.save(prompt)
        prompts = await storage.list()
        assert len(prompts) == 1
        assert prompts[0].name == "test_prompt"

    @pytest.mark.asyncio
    async def test_list_with_tag(self, storage):
        """Test listing prompts with a tag filter."""
        # Create two prompts with different tags
        metadata1 = PromptMetadata(name="prompt1", tags={"tag1"})
        content1 = PromptContent(system="System 1")
        prompt1 = Prompt(metadata=metadata1, content=content1)

        metadata2 = PromptMetadata(name="prompt2", tags={"tag2"})
        content2 = PromptContent(system="System 2")
        prompt2 = Prompt(metadata=metadata2, content=content2)

        await storage.save(prompt1)
        await storage.save(prompt2)

        # List all prompts
        all_prompts = await storage.list()
        assert len(all_prompts) == 2

        # List prompts with tag1
        tag1_prompts = await storage.list(tag="tag1")
        assert len(tag1_prompts) == 1
        assert tag1_prompts[0].name == "prompt1"

        # List prompts with tag2
        tag2_prompts = await storage.list(tag="tag2")
        assert len(tag2_prompts) == 1
        assert tag2_prompts[0].name == "prompt2"

    @pytest.mark.asyncio
    async def test_delete(self, storage, prompt):
        """Test deleting a prompt."""
        await storage.save(prompt)
        result = await storage.delete(prompt.id)
        assert result is True
        loaded_prompt = await storage.load(prompt.id)
        assert loaded_prompt is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        """Test deleting a nonexistent prompt."""
        result = await storage.delete("nonexistent-id")
        assert result is False


class TestFileSystemPromptStorage:
    """Tests for the FileSystemPromptStorage class."""

    @pytest.fixture
    def storage_path(self):
        """Create a temporary directory for storage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def storage(self, storage_path):
        """Create a FileSystemPromptStorage instance."""
        return FileSystemPromptStorage(path=storage_path)

    @pytest.fixture
    def prompt(self):
        """Create a sample prompt."""
        metadata = PromptMetadata(name="test_prompt")
        content = PromptContent(system="You are a helpful assistant.")
        return Prompt(metadata=metadata, content=content)

    @pytest.mark.asyncio
    async def test_save_and_load(self, storage, prompt):
        """Test saving and loading a prompt."""
        await storage.save(prompt)
        loaded_prompt = await storage.load(prompt.id)
        assert loaded_prompt is not None
        assert loaded_prompt.id == prompt.id
        assert loaded_prompt.metadata.name == "test_prompt"
        assert loaded_prompt.content.system == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_list(self, storage, prompt):
        """Test listing prompts."""
        await storage.save(prompt)
        prompts = await storage.list()
        assert len(prompts) == 1
        assert prompts[0].name == "test_prompt"

    @pytest.mark.asyncio
    async def test_list_with_tag(self, storage):
        """Test listing prompts with a tag filter."""
        # Create two prompts with different tags
        metadata1 = PromptMetadata(name="prompt1", tags={"tag1"})
        content1 = PromptContent(system="System 1")
        prompt1 = Prompt(metadata=metadata1, content=content1)

        metadata2 = PromptMetadata(name="prompt2", tags={"tag2"})
        content2 = PromptContent(system="System 2")
        prompt2 = Prompt(metadata=metadata2, content=content2)

        await storage.save(prompt1)
        await storage.save(prompt2)

        # List all prompts
        all_prompts = await storage.list()
        assert len(all_prompts) == 2

        # List prompts with tag1
        tag1_prompts = await storage.list(tag="tag1")
        assert len(tag1_prompts) == 1
        assert tag1_prompts[0].name == "prompt1"

        # List prompts with tag2
        tag2_prompts = await storage.list(tag="tag2")
        assert len(tag2_prompts) == 1
        assert tag2_prompts[0].name == "prompt2"

    @pytest.mark.asyncio
    async def test_delete(self, storage, prompt):
        """Test deleting a prompt."""
        await storage.save(prompt)
        result = await storage.delete(prompt.id)
        assert result is True
        loaded_prompt = await storage.load(prompt.id)
        assert loaded_prompt is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        """Test deleting a nonexistent prompt."""
        result = await storage.delete("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, storage):
        """Test loading a nonexistent prompt."""
        loaded_prompt = await storage.load("nonexistent-id")
        assert loaded_prompt is None


class TestPromptManager:
    """Tests for the PromptManager class."""

    @pytest.fixture
    def manager(self):
        """Create a PromptManager instance with a mock storage."""
        storage = MemoryPromptStorage()
        return PromptManager(storage=storage)

    @pytest.mark.asyncio
    async def test_create_prompt(self, manager):
        """Test creating a prompt."""
        prompt = await manager.create_prompt(
            name="test_prompt",
            description="A test prompt",
            system="You are a helpful assistant.",
            template="Answer the following question: {{question}}",
            examples=[
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "The capital of France is Paris."},
            ],
            tags={"test", "example"},
            author="Test Author",
        )
        assert prompt.metadata.name == "test_prompt"
        assert prompt.metadata.description == "A test prompt"
        assert prompt.content.system == "You are a helpful assistant."
        assert prompt.content.template == "Answer the following question: {{question}}"
        assert len(prompt.content.examples) == 2
        assert prompt.metadata.tags == {"test", "example"}
        assert prompt.metadata.author == "Test Author"

    @pytest.mark.asyncio
    async def test_get_prompt(self, manager):
        """Test getting a prompt by ID."""
        prompt = await manager.create_prompt(name="test_prompt")
        retrieved_prompt = await manager.get_prompt(prompt.id)
        assert retrieved_prompt is not None
        assert retrieved_prompt.id == prompt.id
        assert retrieved_prompt.metadata.name == "test_prompt"

    @pytest.mark.asyncio
    async def test_get_prompt_by_name(self, manager):
        """Test getting a prompt by name."""
        await manager.create_prompt(name="test_prompt")
        retrieved_prompt = await manager.get_prompt_by_name("test_prompt")
        assert retrieved_prompt is not None
        assert retrieved_prompt.metadata.name == "test_prompt"

    @pytest.mark.asyncio
    async def test_update_prompt(self, manager):
        """Test updating a prompt."""
        prompt = await manager.create_prompt(name="test_prompt")
        updated_prompt = await manager.update_prompt(
            prompt.id,
            name="updated_prompt",
            description="Updated description",
            system="Updated system prompt",
            template="Updated template: {{variable}}",
        )
        assert updated_prompt is not None
        assert updated_prompt.metadata.name == "updated_prompt"
        assert updated_prompt.metadata.description == "Updated description"
        assert updated_prompt.content.system == "Updated system prompt"
        assert updated_prompt.content.template == "Updated template: {{variable}}"

    @pytest.mark.asyncio
    async def test_update_nonexistent_prompt(self, manager):
        """Test updating a nonexistent prompt."""
        updated_prompt = await manager.update_prompt(
            "nonexistent-id",
            name="updated_prompt",
        )
        assert updated_prompt is None

    @pytest.mark.asyncio
    async def test_delete_prompt(self, manager):
        """Test deleting a prompt."""
        prompt = await manager.create_prompt(name="test_prompt")
        result = await manager.delete_prompt(prompt.id)
        assert result is True
        retrieved_prompt = await manager.get_prompt(prompt.id)
        assert retrieved_prompt is None

    @pytest.mark.asyncio
    async def test_list_prompts(self, manager):
        """Test listing prompts."""
        await manager.create_prompt(name="prompt1", tags={"tag1"})
        await manager.create_prompt(name="prompt2", tags={"tag2"})
        prompts = await manager.list_prompts()
        assert len(prompts) == 2
        assert {p.name for p in prompts} == {"prompt1", "prompt2"}

    @pytest.mark.asyncio
    async def test_list_prompts_with_tag(self, manager):
        """Test listing prompts with a tag filter."""
        await manager.create_prompt(name="prompt1", tags={"tag1"})
        await manager.create_prompt(name="prompt2", tags={"tag2"})
        prompts = await manager.list_prompts(tag="tag1")
        assert len(prompts) == 1
        assert prompts[0].name == "prompt1"

    @pytest.mark.asyncio
    async def test_render_prompt(self, manager):
        """Test rendering a prompt with context."""
        prompt_id = (await manager.create_prompt(
            name="test_prompt",
            system="You are a helpful assistant.",
            template="Answer the following question: {{question}}",
        )).id
        
        rendered = await manager.render_prompt(
            prompt_id,
            context={"question": "What is the capital of France?"},
        )
        
        assert rendered is not None
        assert rendered["system"] == "You are a helpful assistant."
        assert rendered["content"] == "Answer the following question: What is the capital of France?"

    @pytest.mark.asyncio
    async def test_render_prompt_with_system_override(self, manager):
        """Test rendering a prompt with a system prompt override."""
        prompt_id = (await manager.create_prompt(
            name="test_prompt",
            system="You are a helpful assistant.",
            template="Answer the following question: {{question}}",
        )).id
        
        rendered = await manager.render_prompt(
            prompt_id,
            context={"question": "What is the capital of France?"},
            system_override="You are a knowledgeable geography expert.",
        )
        
        assert rendered is not None
        assert rendered["system"] == "You are a knowledgeable geography expert."
        assert rendered["content"] == "Answer the following question: What is the capital of France?"

    @pytest.mark.asyncio
    async def test_render_nonexistent_prompt(self, manager):
        """Test rendering a nonexistent prompt."""
        rendered = await manager.render_prompt("nonexistent-id")
        assert rendered is None 