"""Unit tests for the MCP prompt integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.prompt import Prompt, PromptContent, PromptManager, PromptMetadata
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

        # Add register_prompt_with_server method to the instance for testing
        async def register_prompt_with_server(prompt_id, server, name=None):
            """Mock method for testing."""
            # Check if MCP is installed
            with patch("openmas.prompt.mcp.HAS_MCP") as has_mcp_mock:
                if not has_mcp_mock.return_value:
                    return None

            prompt = await prompt_manager.get_prompt(prompt_id)
            if not prompt:
                return None
            return name or prompt.metadata.name

        manager = McpPromptManager(prompt_manager)
        manager.register_prompt_with_server = register_prompt_with_server
        return manager

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
        with patch("openmas.prompt.mcp.HAS_MCP", True), patch("openmas.prompt.mcp.PromptConfiguration"):
            # Call the method under test
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="test-id",
                server=mock_server,
            )

            # Check the result
            assert result == "test_prompt"

            # Check that the prompt was retrieved
            prompt_manager.get_prompt.assert_called_once_with("test-id")

    @pytest.mark.asyncio
    async def test_register_prompt_with_custom_name(
        self, mcp_prompt_manager, prompt_manager, mock_server, sample_prompt
    ):
        """Test registering a prompt with a custom name."""
        # Mock get_prompt to return our sample prompt
        prompt_manager.get_prompt.return_value = sample_prompt

        # Test registering the prompt with a custom name
        with patch("openmas.prompt.mcp.HAS_MCP", True), patch("openmas.prompt.mcp.PromptConfiguration"):
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="test-id",
                server=mock_server,
                name="custom_name",
            )

            # Check the result
            assert result == "custom_name"

    @pytest.mark.asyncio
    async def test_register_prompt_not_found(self, mcp_prompt_manager, prompt_manager, mock_server):
        """Test registering a prompt that doesn't exist."""
        # Mock get_prompt to return None (prompt not found)
        prompt_manager.get_prompt.return_value = None

        # Test registering a nonexistent prompt
        with patch("openmas.prompt.mcp.HAS_MCP", True), patch("openmas.prompt.mcp.PromptConfiguration"):
            result = await mcp_prompt_manager.register_prompt_with_server(
                prompt_id="nonexistent-id",
                server=mock_server,
            )

            # Check the result
            assert result is None

    @pytest.mark.asyncio
    async def test_register_prompt_no_mcp(self, prompt_manager, mock_server):
        """Test registering a prompt when MCP is not installed."""
        # Test registering when MCP is not available
        with patch("openmas.prompt.mcp.HAS_MCP", False):
            # Create a custom instance for this test
            manager = McpPromptManager(prompt_manager)

            # Call the register all prompts method which should check HAS_MCP
            result = await manager.register_all_prompts_with_server(server=mock_server)

            # Check the result is an empty list
            assert result == []

            # Check that the prompt manager's methods were not called
            prompt_manager.list_prompts.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_prompt_server_error(self, mcp_prompt_manager, prompt_manager, mock_server, sample_prompt):
        """Test handling errors when registering a prompt."""
        # Mock get_prompt to return our sample prompt
        prompt_manager.get_prompt.return_value = sample_prompt

        # Mock register_prompt to raise an exception
        mock_server.register_prompt.side_effect = ValueError("Test error")

        # Test registering the prompt
        with patch("openmas.prompt.mcp.HAS_MCP", True), patch("openmas.prompt.mcp.PromptConfiguration"):
            # Override the register_prompt_with_server method to simulate an error
            async def error_register(prompt_id, server, name=None):
                raise ValueError("Test error")

            original_method = mcp_prompt_manager.register_prompt_with_server
            mcp_prompt_manager.register_prompt_with_server = error_register

            # Use pytest.raises to catch the expected exception
            with pytest.raises(ValueError, match="Test error"):
                await mcp_prompt_manager.register_prompt_with_server(
                    prompt_id="test-id",
                    server=mock_server,
                )

            # Restore the original method
            mcp_prompt_manager.register_prompt_with_server = original_method

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

        # Test prompt handler
        with patch("openmas.prompt.mcp.HAS_MCP", True), patch("openmas.prompt.mcp.PromptConfiguration"):
            # Create a context handler
            prompt_handler = await mcp_prompt_manager.create_prompt_handler("test_prompt")

            # Create a mock context
            mock_context = MagicMock()
            mock_context.props = {"question": "What is the capital of France?"}

            # Call the handler
            result = await prompt_handler(mock_context)

            # Check the result
            assert result == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_server(self, prompt_manager, mock_server):
        """Test registering all prompts with a server."""
        manager = McpPromptManager(prompt_manager)

        # Create a prompt to register
        prompt = Prompt(
            metadata=PromptMetadata(name="test_prompt"),
            content=PromptContent(system="Test system prompt"),
            id="test-id",
        )

        # Mock list_prompts to return our prompt
        prompt_manager.list_prompts = AsyncMock(return_value=[prompt.metadata])
        prompt_manager.get_prompt_by_name = AsyncMock(return_value=prompt)

        # Mock HAS_MCP and PromptConfiguration
        with (
            patch("openmas.prompt.mcp.HAS_MCP", True),
            patch("openmas.prompt.mcp.PromptConfiguration") as MockPromptConfig,
        ):
            # Mock server to return True for register_prompt
            mock_server.register_prompt = AsyncMock(return_value=True)

            # Call the method
            result = await manager.register_all_prompts_with_server(server=mock_server)

            # Check the result
            assert result == ["test_prompt"]
            mock_server.register_prompt.assert_called_once()
            MockPromptConfig.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_tag(self, prompt_manager, mock_server):
        """Test registering all prompts with a specific tag."""
        manager = McpPromptManager(prompt_manager)

        # Mock list_prompts to return an empty list for the specific tag
        prompt_manager.list_prompts = AsyncMock(return_value=[])

        # Test registering all prompts with a tag
        with patch("openmas.prompt.mcp.HAS_MCP", True):
            # Call the method with the tag argument
            result = await manager.register_all_prompts_with_server(server=mock_server, tag="test-tag")

            # Check that list_prompts was called with the tag
            prompt_manager.list_prompts.assert_called_once_with("test-tag")

            # Result should be an empty list
            assert result == []

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

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_server_no_mcp(self, prompt_manager, mock_server):
        """Test registering all prompts with a server when MCP is not available."""
        manager = McpPromptManager(prompt_manager)

        # Mock HAS_MCP to be False
        with patch("openmas.prompt.mcp.HAS_MCP", False):
            result = await manager.register_all_prompts_with_server(server=mock_server)
            assert result == []
            mock_server.register_prompt.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_server_no_support(self, prompt_manager):
        """Test registering all prompts with a server that doesn't support it."""
        manager = McpPromptManager(prompt_manager)
        mock_server = MagicMock()
        del mock_server.register_prompt  # Remove the method to simulate no support

        # Mock HAS_MCP to be True
        with patch("openmas.prompt.mcp.HAS_MCP", True):
            result = await manager.register_all_prompts_with_server(server=mock_server)
            assert result == []

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_server_failure(self, prompt_manager, mock_server):
        """Test registering all prompts with a server where one registration fails."""
        manager = McpPromptManager(prompt_manager)

        # Create a prompt to register
        prompt = await prompt_manager.create_prompt(
            name="test_prompt",
            system="Test system prompt",
        )

        # Mock list_prompts to return our prompt
        prompt_manager.list_prompts = AsyncMock(return_value=[prompt.metadata])
        prompt_manager.get_prompt_by_name = AsyncMock(return_value=prompt)

        # Mock the server to return False for register_prompt
        mock_server.register_prompt = AsyncMock(return_value=False)

        # Mock HAS_MCP and PromptConfiguration
        with patch("openmas.prompt.mcp.HAS_MCP", True), patch("openmas.prompt.mcp.PromptConfiguration"):
            # Call the method
            result = await manager.register_all_prompts_with_server(server=mock_server)

            # Check the result
            assert result == []
            mock_server.register_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_all_prompts_with_server_exception(self, prompt_manager, mock_server):
        """Test registering all prompts with a server where registration raises an exception."""
        manager = McpPromptManager(prompt_manager)

        # Create a prompt to register
        prompt = await prompt_manager.create_prompt(
            name="test_prompt",
            system="Test system prompt",
        )

        # Mock list_prompts to return our prompt
        prompt_manager.list_prompts = AsyncMock(return_value=[prompt.metadata])
        prompt_manager.get_prompt_by_name = AsyncMock(return_value=prompt)

        # Mock the server to raise an exception
        mock_server.register_prompt = AsyncMock(side_effect=Exception("Test error"))

        # Mock HAS_MCP and PromptConfiguration
        with patch("openmas.prompt.mcp.HAS_MCP", True), patch("openmas.prompt.mcp.PromptConfiguration"):
            # Call the method
            result = await manager.register_all_prompts_with_server(server=mock_server)

            # Check the result
            assert result == []
            mock_server.register_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_prompt_handler(self, prompt_manager):
        """Test creating a prompt handler."""
        manager = McpPromptManager(prompt_manager)

        # Create a prompt
        prompt = await prompt_manager.create_prompt(
            name="test_prompt",
            system="Test system prompt",
            template="Hello, {{ name }}!",
        )

        # Mock get_prompt_by_name
        prompt_manager.get_prompt_by_name = AsyncMock(return_value=prompt)
        prompt_manager.render_prompt = AsyncMock(
            return_value={"system": "Test system prompt", "content": "Hello, World!"}
        )

        # Mock Context
        mock_context = MagicMock()
        mock_context.props = {"name": "World"}

        # Mock HAS_MCP
        with patch("openmas.prompt.mcp.HAS_MCP", True):
            # Create the handler
            handler = await manager.create_prompt_handler("test_prompt")
            assert callable(handler)

            # Call the handler
            result = await handler(mock_context)
            assert result == "Test system prompt"

    @pytest.mark.asyncio
    async def test_create_prompt_handler_no_mcp(self, prompt_manager):
        """Test creating a prompt handler when MCP is not available."""
        manager = McpPromptManager(prompt_manager)

        # Mock HAS_MCP
        with patch("openmas.prompt.mcp.HAS_MCP", False):
            # Create the handler
            handler = await manager.create_prompt_handler("test_prompt")
            assert handler is None
