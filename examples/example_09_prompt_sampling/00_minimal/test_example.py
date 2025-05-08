"""Test for the MCP prompt and sampling example."""

import pytest
from agents.prompt_sampling_agent import PromptSamplingAgent

from openmas.config import AgentConfig
from openmas.prompt.base import PromptConfig
from openmas.sampling.base import SamplingParameters
from openmas.testing import AgentTestHarness


@pytest.mark.asyncio
async def test_prompt_sampling_agent_runs_and_renders_prompt(tmp_path):
    # Setup temp prompts dir and file
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompt_file = prompts_dir / "summarize.txt"
    prompt_file.write_text("Summarize the following text: {{text_to_summarize}}", encoding="utf-8")

    # Build AgentConfig with all fields
    agent_config = AgentConfig(
        name="prompt_sampling_agent",
        prompts_dir="prompts",
        prompts=[
            PromptConfig(name="summarize_text", template_file="summarize.txt", input_variables=["text_to_summarize"])
        ],
        sampling=SamplingParameters(provider="mock", model="test-model", temperature=0.5),
        communicator_type="mock",
        service_urls={},
        log_level="INFO",
    )

    # Only pass name to create_agent, and put the rest in default_config
    default_config = agent_config.model_dump()
    harness = AgentTestHarness(PromptSamplingAgent, default_config=default_config, project_root=tmp_path)
    agent = await harness.create_agent(name=agent_config.name)
    async with harness.running_agent(agent):
        assert agent.project_root == tmp_path  # Verify project_root is set correctly
        assert hasattr(agent, "prompt_manager")
        assert agent.prompt_manager is not None
        assert hasattr(agent, "sampler")
        assert agent.prompt_manager._prompts.get("summarize_text") is not None
