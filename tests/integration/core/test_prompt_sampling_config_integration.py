"""Integration tests for the prompt and sampling config in the OpenMAS CLI."""

import os
import subprocess
import sys

import pytest
import yaml


@pytest.fixture
def prompt_sampling_project(tmp_path):
    """Create a sample OpenMAS project with prompt and sampling config for integration testing."""
    project_dir = tmp_path / "prompt_sampling_project"
    project_dir.mkdir()

    # Create agent directory
    agent_dir = project_dir / "agents" / "prompt_agent"
    agent_dir.mkdir(parents=True)

    # Write a minimal agent that prints its config
    agent_file = agent_dir / "agent.py"
    agent_file.write_text(
        """
import asyncio
from openmas.agent import BaseAgent

class PromptAgent(BaseAgent):
    async def setup(self):
        print(f"PROMPTS: {self.config.prompts}")
        print(f"PROMPTS_DIR: {self.config.prompts_dir}")
        print(f"SAMPLING: {self.config.sampling}")
    async def run(self):
        print("RUNNING")
        await asyncio.sleep(0.1)
    async def shutdown(self):
        print("SHUTDOWN")
"""
    )

    # Create openmas_project.yml with prompts and sampling
    project_config = {
        "name": "prompt_sampling_project",
        "version": "0.1.0",
        "agents": {
            "prompt_agent": {
                "module": "agents.prompt_agent.agent",
                "class": "PromptAgent",
                "prompts_dir": "custom_prompts",
                "prompts": [
                    {
                        "name": "summarize_text",
                        "template_file": "summarize.txt",
                        "input_variables": ["text_to_summarize"],
                    },
                    {
                        "name": "generate_greeting",
                        "template": "Hello, {{user_name}}! Welcome to {{service}}.",
                        "input_variables": ["user_name", "service"],
                    },
                ],
                "sampling": {
                    "provider": "mcp",
                    "model": "claude-3-sonnet-20240229",
                    "temperature": 0.5,
                    "max_tokens": 150,
                },
            }
        },
        "default_config": {"log_level": "INFO", "communicator_type": "http"},
    }
    with open(project_dir / "openmas_project.yml", "w") as f:
        yaml.dump(project_config, f)

    # Create the custom prompts directory and a template file
    prompts_dir = project_dir / "custom_prompts"
    prompts_dir.mkdir()
    (prompts_dir / "summarize.txt").write_text("Summarize: {{text_to_summarize}}")

    return project_dir


@pytest.mark.integration
def test_agent_receives_prompt_and_sampling_config(prompt_sampling_project):
    """Integration test: agent receives correct prompt and sampling config from project YAML."""
    project_dir = prompt_sampling_project
    agent_module = "agents.prompt_agent.agent"
    agent_class = "PromptAgent"

    # Write a minimal runner script to instantiate and run the agent
    runner_file = project_dir / "run_agent.py"
    runner_file.write_text(
        f"""
import sys
import asyncio
from openmas.config import ProjectConfig, AgentConfig
from importlib import import_module
import yaml
from pathlib import Path

if __name__ == "__main__":
    # Load the project config YAML
    with open("openmas_project.yml", "r") as f:
        project_data = yaml.safe_load(f)
    project_config = ProjectConfig(**project_data)
    agent_entry = project_config.agents["prompt_agent"]
    # Merge agent-specific config fields for AgentConfig
    agent_config_dict = {{"name": "prompt_agent"}}
    # Add fields if present in agent_entry
    for field in ["prompts", "prompts_dir", "sampling"]:
        if hasattr(agent_entry, field):
            value = getattr(agent_entry, field)
            if value is not None:
                agent_config_dict[field] = value
        elif field in agent_entry.__dict__:
            value = agent_entry.__dict__[field]
            if value is not None:
                agent_config_dict[field] = value
    config = AgentConfig(**agent_config_dict)
    mod = import_module("{agent_module}")
    agent_cls = getattr(mod, "{agent_class}")
    agent = agent_cls(name=config.name, config=config)
    async def main():
        await agent.setup()
        await agent.run()
        await agent.shutdown()
    asyncio.run(main())
"""
    )

    # Run the agent in a subprocess, simulating CLI usage
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_dir)
    env["AGENT_NAME"] = "prompt_agent"
    proc = subprocess.run(
        [sys.executable, str(runner_file)],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    print("STDOUT:\n", proc.stdout)
    print("STDERR:\n", proc.stderr)
    assert proc.returncode == 0
    # Check that the config fields are present in output
    assert "PROMPTS: [" in proc.stdout
    assert "PROMPTS_DIR: custom_prompts" in proc.stdout
    assert "SAMPLING: " in proc.stdout
    assert "provider='mcp'" in proc.stdout
    assert "model='claude-3-sonnet-20240229'" in proc.stdout
    assert "temperature=0.5" in proc.stdout
    assert "max_tokens=150" in proc.stdout
