"""Unit tests for the MCP prompt integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openmas.prompt import PromptManager, PromptMetadata, PromptContent, Prompt
from openmas.prompt.mcp import McpPromptManager


class TestMcpPromptManager:
    """Tests for the McpPromptManager class."""

    @pytest.fixture
    def prompt_manager(self):
        """Create a PromptManager instance with mocked storage."""
        manager = PromptManager()
        manager.create_prompt = AsyncMock()
        manager.get_prompt = AsyncMock()
        manager.get_prompt_by_name = AsyncMock()
        manager.list_prompts = AsyncMock()
        manager.render_prompt = AsyncMock()
        return manager

    @pytest.fixture
    def mcp_prompt_manager(self, prompt_manager):
        """Create an McpPromptManager instance."""
        return McpPromptManager(prompt_manager)

    @pytest.fixture
    def mock_server(self):
        """Create a mock MCP server."""
        server = MagicMock()
        server.register_prompt = AsyncMock()
        return server

    @pytest.fixture
    def sample_prompt(self):
        """Create a sample prompt."""
        metadata = PromptMetadata(
            name="test_prompt",
            description="A test prompt",
        )
        content = PromptContent(
            system="You are a helpful assistant.",
            template="Answer the following question: {{question}}",
        )
        return Prompt(metadata=metadata, content=content, id="test-id")

    @pytest.mark.asyncio
    async def test_register_prompt_with_server(self, mcp_prompt_manager, prompt_manager, mock_server, sample_prompt):
        """Test registering a prompt with an MCP server."""
        # Mock get_prompt to return our sample prompt
        prompt_manager.get_prompt.return_value = sample_prompt

        # Test registering the prompt
        with patch("openmas.prompt.mcp.HAS_MCP", True), \
             patch("openmas.prompt.mcp.McpPrompt") as MockMcpPrompt:
            
            # Configure the mock to behave like the real McpPrompt
            mock_mcp_prompt = MagicMock()
            MockMcpPrompt.return_value = mock_mcp_prompt
            
            # Call the method under test
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="test-id",
                server=mock_server,
            )
            
            # Check the result
            assert result == "test_prompt"
            
            # Check that the prompt was retrieved
            prompt_manager.get_prompt.assert_called_once_with("test-id")
            
            # Check that McpPrompt was created
            MockMcpPrompt.assert_called_once()
            fn_arg = MockMcpPrompt.call_args.kwargs["fn"]
            assert callable(fn_arg)
            
            # Check that register_prompt was called
            mock_server.register_prompt.assert_called_once_with("test_prompt", mock_mcp_prompt)

    @pytest.mark.asyncio
    async def test_register_prompt_with_custom_name(self, mcp_prompt_manager, prompt_manager, mock_server, sample_prompt):
        """Test registering a prompt with a custom name."""
        # Mock get_prompt to return our sample prompt
        prompt_manager.get_prompt.return_value = sample_prompt

        # Test registering the prompt with a custom name
        with patch("openmas.prompt.mcp.HAS_MCP", True), \
             patch("openmas.prompt.mcp.McpPrompt") as MockMcpPrompt:
            
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="test-id",
                server=mock_server,
                name="custom_name",
            )
            
            # Check the result
            assert result == "custom_name"
            
            # Check that register_prompt was called with the custom name
            mock_server.register_prompt.assert_called_once()
            assert mock_server.register_prompt.call_args.args[0] == "custom_name"

    @pytest.mark.asyncio
    async def test_register_prompt_not_found(self, mcp_prompt_manager, prompt_manager, mock_server):
        """Test registering a prompt that doesn't exist."""
        # Mock get_prompt to return None (prompt not found)
        prompt_manager.get_prompt.return_value = None

        # Test registering a nonexistent prompt
        with patch("openmas.prompt.mcp.HAS_MCP", True), \
             patch("openmas.prompt.mcp.McpPrompt") as MockMcpPrompt:
            
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="nonexistent-id",
                server=mock_server,
            )
            
            # Check the result
            assert result is None
            
            # Check that register_prompt was not called
            mock_server.register_prompt.assert_not_called()
            MockMcpPrompt.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_prompt_no_mcp(self, mcp_prompt_manager, prompt_manager, mock_server):
        """Test registering a prompt when MCP is not installed."""
        # Test registering when MCP is not available
        with patch("openmas.prompt.mcp.HAS_MCP", False):
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="test-id",
                server=mock_server,
            )
            
            # Check the result
            assert result is None
            
            # Check that get_prompt was not called
            prompt_manager.get_prompt.assert_not_called()
            
            # Check that register_prompt was not called
            mock_server.register_prompt.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_prompt_server_error(self, mcp_prompt_manager, prompt_manager, mock_server, sample_prompt):
        """Test handling errors when registering a prompt."""
        # Mock get_prompt to return our sample prompt
        prompt_manager.get_prompt.return_value = sample_prompt
        
        # Mock register_prompt to raise an exception
        mock_server.register_prompt.side_effect = ValueError("Test error")

        # Test registering the prompt
        with patch("openmas.prompt.mcp.HAS_MCP", True), \
             patch("openmas.prompt.mcp.McpPrompt"):
            
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="test-id",
                server=mock_server,
            )
            
            # Check the result
            assert result is None

    @pytest.mark.asyncio
    async def test_register_prompt_handler(self, mcp_prompt_manager, prompt_manager, mock_server, sample_prompt):
        """Test the prompt handler function created for registration."""
        # Mock get_prompt to return our sample prompt
        prompt_manager.get_prompt.return_value = sample_prompt
        
        # Mock render_prompt to return a rendered prompt
        prompt_manager.render_prompt.return_value = {
            "system": "You are a helpful assistant.",
            "content": "Answer the following question: What is the capital of France?",
        }

        # Test registering the prompt
        with patch("openmas.prompt.mcp.HAS_MCP", True), \
             patch("openmas.prompt.mcp.McpPrompt") as MockMcpPrompt:
            
            # Call the method under test
            await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="test-id",
                server=mock_server,
            )
            
            # Get the handler function
            handler_fn = MockMcpPrompt.call_args.kwargs["fn"]
            
            # Call the handler function
            result = await handler_fn(question="What is the capital of France?")
            
            # Check that render_prompt was called
            prompt_manager.render_prompt.assert_called_once_with(
                "test-id",
                context={"question": "What is the capital of France?"},
            )
            
            # Check the result
            assert result == "You are a helpful assistant.\n\nAnswer the following question: What is the capital of France?"

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_server(self, mcp_prompt_manager, prompt_manager, mock_server, sample_prompt):
        """Test registering all prompts with an MCP server."""
        # Mock list_prompts to return metadata for our sample prompt
        prompt_manager.list_prompts.return_value = [sample_prompt.metadata]
        
        # Mock get_prompt_by_name to return our sample prompt
        prompt_manager.get_prompt_by_name.return_value = sample_prompt

        # Test registering all prompts
        with patch("openmas.prompt.mcp.HAS_MCP", True), \
             patch("openmas.prompt.mcp.McpPrompt"):
            
            # Configure register_prompt_with_server to return the prompt name
            mcp_prompt_manager.register_prompt_with_server = AsyncMock(return_value="test_prompt")
            
            # Call the method under test
            result = await mcp_prompt_manager.register_all_prompts_with_server(mock_server)
            
            # Check the result
            assert result == ["test_prompt"]
            
            # Check that list_prompts was called
            prompt_manager.list_prompts.assert_called_once_with(tag=None)
            
            # Check that get_prompt_by_name was called
            prompt_manager.get_prompt_by_name.assert_called_once_with("test_prompt")
            
            # Check that register_prompt_with_server was called
            mcp_prompt_manager.register_prompt_with_server.assert_called_once_with(
                "test-id",
                mock_server,
            )

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_tag(self, mcp_prompt_manager, prompt_manager, mock_server):
        """Test registering all prompts with a specific tag."""
        # Mock list_prompts to return an empty list for the specific tag
        prompt_manager.list_prompts.return_value = []

        # Test registering all prompts with a tag
        with patch("openmas.prompt.mcp.HAS_MCP", True):
            result = await mcp_prompt_manager.register_all_prompts_with_server(
                server=mock_server,
                tag="test-tag",
            )
            
            # Check the result
            assert result == []
            
            # Check that list_prompts was called with the tag
            prompt_manager.list_prompts.assert_called_once_with(tag="test-tag")

    @pytest.mark.asyncio
    async def test_register_all_prompts_no_mcp(self, mcp_prompt_manager, prompt_manager, mock_server):
        """Test registering all prompts when MCP is not installed."""
        # Test registering when MCP is not available
        with patch("openmas.prompt.mcp.HAS_MCP", False):
            result = await mcp_prompt_manager.register_all_prompts_with_server(mock_server)
            
            # Check the result
            assert result == []
            
            # Check that list_prompts was not called
            prompt_manager.list_prompts.assert_not_called() 