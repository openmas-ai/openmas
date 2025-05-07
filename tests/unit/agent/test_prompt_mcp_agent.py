"""Unit tests for the PromptMcpAgent class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.agent.mcp_prompt import PromptMcpAgent
from openmas.config import AgentConfig
from openmas.prompt.base import Prompt, PromptContent, PromptManager, PromptMetadata
from openmas.sampling import SamplingResult


class TestPromptMcpAgent:
    """Tests for the PromptMcpAgent class."""

    @pytest.fixture
    def communicator(self):
        """Create a mock communicator."""
        mock_communicator = MagicMock()
        mock_communicator.sample_prompt = AsyncMock(return_value={"content": "Generated response"})
        mock_communicator.register_prompt = AsyncMock()
        return mock_communicator

    @pytest.fixture
    def agent(self, communicator):
        """Create a PromptMcpAgent instance."""
        # Create a config object to use with patching load_config
        config = AgentConfig(name="test-agent", service_urls={})

        # Patch load_config to avoid validation errors
        with patch("openmas.agent.base.load_config", return_value=config):
            agent = PromptMcpAgent(
                name="test-agent",
                llm_service="llm-service",
                default_model="claude-3",
            )
            agent.communicator = communicator
            return agent

    def test_initialization(self):
        """Test initialization of PromptMcpAgent."""
        # Create a config object to use with patching load_config
        config = AgentConfig(name="test-agent", service_urls={})

        # Patch load_config to avoid validation errors
        with patch("openmas.agent.base.load_config", return_value=config):
            agent = PromptMcpAgent(
                name="test-agent",
                llm_service="llm-service",
                default_model="claude-3",
            )
            assert agent.name == "test-agent"
            assert agent._llm_service == "llm-service"
            assert agent._default_model == "claude-3"
            assert agent.prompt_manager is not None
            assert agent.mcp_prompt_manager is not None
            assert agent._sampler is None

    def test_initialization_with_prompt_manager(self):
        """Test initialization with a custom prompt manager."""
        # Create a config object to use with patching load_config
        config = AgentConfig(name="test-agent", service_urls={})

        # Patch load_config to avoid validation errors
        with patch("openmas.agent.base.load_config", return_value=config):
            prompt_manager = PromptManager()
            agent = PromptMcpAgent(
                name="test-agent",
                prompt_manager=prompt_manager,
            )
            assert agent.prompt_manager is prompt_manager

    @pytest.mark.asyncio
    async def test_setup(self, agent, communicator):
        """Test setup method."""
        # Mock the parent setup method
        with patch("openmas.agent.mcp.McpAgent.setup", AsyncMock()) as mock_setup:
            await agent.setup()

            # Check that parent setup was called
            mock_setup.assert_called_once()

            # Check that a sampler was created
            assert agent._sampler is not None
            assert agent._sampler.agent is agent
            assert agent._sampler.target_service == "llm-service"
            assert agent._sampler.default_model == "claude-3"

    @pytest.mark.asyncio
    async def test_register_prompts_with_server_not_server_mode(self, agent):
        """Test register_prompts_with_server when not in server mode."""
        # Set server_mode to False
        agent._server_mode = False

        # Mock the mcp_prompt_manager.register_all_prompts_with_server method
        agent.mcp_prompt_manager.register_all_prompts_with_server = AsyncMock()

        # Call the method
        await agent.register_prompts_with_server()

        # Check that register_all_prompts_with_server was not called
        agent.mcp_prompt_manager.register_all_prompts_with_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_prompts_with_server(self, agent, communicator):
        """Test register_prompts_with_server in server mode."""
        # Set server_mode to True
        agent._server_mode = True

        # Mock the mcp_prompt_manager.register_all_prompts_with_server method
        agent.mcp_prompt_manager.register_all_prompts_with_server = AsyncMock(return_value=["prompt1", "prompt2"])

        # Call the method
        await agent.register_prompts_with_server()

        # Check that register_all_prompts_with_server was called
        agent.mcp_prompt_manager.register_all_prompts_with_server.assert_called_once_with(server=communicator)

    @pytest.mark.asyncio
    async def test_register_prompts_with_server_no_communicator(self, agent):
        """Test register_prompts_with_server with no communicator."""
        # Set server_mode to True but remove the communicator
        agent._server_mode = True
        agent.communicator = None

        # Mock the mcp_prompt_manager.register_all_prompts_with_server method
        agent.mcp_prompt_manager.register_all_prompts_with_server = AsyncMock()

        # Call the method
        await agent.register_prompts_with_server()

        # Check that register_all_prompts_with_server was not called
        agent.mcp_prompt_manager.register_all_prompts_with_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_prompts_with_server_no_register_prompt(self, agent, communicator):
        """Test register_prompts_with_server with a communicator that doesn't support register_prompt."""
        # Set server_mode to True and remove the register_prompt method from the communicator
        agent._server_mode = True
        del communicator.register_prompt

        # Mock the mcp_prompt_manager.register_all_prompts_with_server method
        agent.mcp_prompt_manager.register_all_prompts_with_server = AsyncMock()

        # Call the method
        await agent.register_prompts_with_server()

        # Check that register_all_prompts_with_server was not called
        agent.mcp_prompt_manager.register_all_prompts_with_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_prompt(self, agent):
        """Test create_prompt method."""
        # Mock the prompt_manager.create_prompt method
        sample_prompt = Prompt(
            metadata=PromptMetadata(name="test_prompt"),
            content=PromptContent(system="Test system prompt"),
        )
        agent.prompt_manager.create_prompt = AsyncMock(return_value=sample_prompt)

        # Call the method
        result = await agent.create_prompt(
            name="test_prompt",
            system="Test system prompt",
        )

        # Check that create_prompt was called with the correct arguments
        agent.prompt_manager.create_prompt.assert_called_once_with(
            name="test_prompt",
            description=None,
            system="Test system prompt",
            template=None,
            examples=None,
            tags=None,
            author=None,
        )

        # Check the result
        assert result is sample_prompt

    @pytest.mark.asyncio
    async def test_render_prompt(self, agent):
        """Test render_prompt method."""
        # Mock the prompt_manager.render_prompt method
        rendered_prompt = {
            "system": "Test system prompt",
            "content": "Test content",
        }
        agent.prompt_manager.render_prompt = AsyncMock(return_value=rendered_prompt)

        # Call the method
        result = await agent.render_prompt(
            prompt_id="test-id",
            context={"key": "value"},
            system_override="Override system prompt",
        )

        # Check that render_prompt was called with the correct arguments
        agent.prompt_manager.render_prompt.assert_called_once_with(
            prompt_id="test-id",
            context={"key": "value"},
            system_override="Override system prompt",
        )

        # Check the result
        assert result is rendered_prompt

    @pytest.mark.asyncio
    async def test_sample_with_existing_sampler(self, agent):
        """Test sample method with an existing sampler."""
        # Create a mock sampler
        mock_sampler = MagicMock()
        mock_sampler.sample_from_prompt = AsyncMock(return_value=SamplingResult(content="Generated response"))
        agent._sampler = mock_sampler

        # Mock getting the prompt
        sample_prompt = Prompt(
            metadata=PromptMetadata(name="test_prompt"),
            content=PromptContent(system="Test system prompt"),
        )
        agent.prompt_manager.get_prompt = AsyncMock(return_value=sample_prompt)

        # Call the method
        result = await agent.sample(
            prompt_id="test-id",
            context={"key": "value"},
            parameters={"temperature": 0.5},
            model="claude-3",
        )

        # Check that get_prompt was called
        agent.prompt_manager.get_prompt.assert_called_once_with("test-id")

        # Check that sample_from_prompt was called
        mock_sampler.sample_from_prompt.assert_called_once_with(
            prompt=sample_prompt,
            context_vars={"key": "value"},
            parameters={"temperature": 0.5},
            model="claude-3",
        )

        # Check the result
        assert result.content == "Generated response"

    @pytest.mark.asyncio
    async def test_sample_create_sampler(self, agent, communicator):
        """Test sample method creating a sampler on demand."""
        # Ensure no sampler exists
        agent._sampler = None

        # Mock getting the prompt
        sample_prompt = Prompt(
            metadata=PromptMetadata(name="test_prompt"),
            content=PromptContent(system="Test system prompt"),
        )
        agent.prompt_manager.get_prompt = AsyncMock(return_value=sample_prompt)

        # Create a mock for McpAgentSampler
        with patch("openmas.agent.mcp_prompt.McpAgentSampler") as MockSampler:
            # Configure the mock sampler
            mock_sampler = MagicMock()
            mock_sampler.sample_from_prompt = AsyncMock(return_value=SamplingResult(content="Generated response"))
            MockSampler.return_value = mock_sampler

            # Call the method
            result = await agent.sample(
                prompt_id="test-id",
                context={"key": "value"},
            )

            # Check that a sampler was created
            MockSampler.assert_called_once_with(
                agent=agent,
                target_service="llm-service",
                default_model="claude-3",
            )

            # Check that sample_from_prompt was called
            mock_sampler.sample_from_prompt.assert_called_once()

            # Check the result
            assert result.content == "Generated response"

            # Check that the sampler was stored
            assert agent._sampler is mock_sampler

    @pytest.mark.asyncio
    async def test_sample_text(self, agent, communicator):
        """Test sample_text method."""
        # Create a mock sampler
        mock_sampler = MagicMock()
        mock_result = SamplingResult(content="Generated response")
        mock_sampler.sample = AsyncMock(return_value=mock_result)
        mock_sampler.create_context = MagicMock()
        agent._sampler = mock_sampler

        # Call the method
        result = await agent.sample_text(
            system="Test system prompt",
            prompt="Test prompt",
            parameters={"temperature": 0.5},
            model="claude-3",
        )

        # Check that create_context was called
        mock_sampler.create_context.assert_called_once()

        # Check that sample was called
        mock_sampler.sample.assert_called_once()

        # Check the result
        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_chat(self, agent, communicator):
        """Test chat method."""
        # Create a mock sampler
        mock_sampler = MagicMock()
        mock_result = SamplingResult(content="Generated response")
        mock_sampler.sample = AsyncMock(return_value=mock_result)
        mock_sampler.create_context = MagicMock()
        agent._sampler = mock_sampler

        # Call the method
        result = await agent.chat(
            system="Test system prompt",
            messages=[{"role": "user", "content": "Hello"}],
            parameters={"temperature": 0.5},
            model="claude-3",
        )

        # Check that create_context was called
        mock_sampler.create_context.assert_called_once_with(
            system="Test system prompt",
            messages=[{"role": "user", "content": "Hello"}],
            parameters={"temperature": 0.5},
        )

        # Check that sample was called
        mock_sampler.sample.assert_called_once()

        # Check the result
        assert result is mock_result
