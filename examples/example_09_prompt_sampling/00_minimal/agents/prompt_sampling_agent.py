"""Prompt and Sampling agent."""

import asyncio

from openmas.agent import BaseAgent
from openmas.prompt import PromptManager
from openmas.sampling import SamplingParameters, get_sampler


class PromptSamplingAgent(BaseAgent):
    async def setup(self) -> None:
        self.logger.info("Setting up PromptSamplingAgent")
        self.logger.info(f"self.config: {self.config}")
        self.logger.info(f"self.config.prompts: {self.config.prompts} (type: {type(self.config.prompts)})")
        self.logger.info(f"self.config.prompts_dir: {self.config.prompts_dir} (type: {type(self.config.prompts_dir)})")
        self.logger.info(f"self.config.sampling: {self.config.sampling} (type: {type(self.config.sampling)})")
        if not self.config.prompts:
            raise RuntimeError(f"Agent config.prompts is missing or empty: {self.config}")
        # Initialize PromptManager
        self.prompt_manager = PromptManager(
            prompts_base_path=self.project_root / (self.config.prompts_dir or "prompts")
        )
        self.prompt_manager.load_prompts_from_config(self.config.prompts)
        # Initialize Sampler
        self.sampler = None
        if self.config.sampling:
            params = SamplingParameters(**self.config.sampling.model_dump(exclude_none=True))
            self.sampler = get_sampler(params=params)

    async def run(self) -> None:
        self.logger.info("Running PromptSamplingAgent")
        if not self.prompt_manager or not self.sampler:
            self.logger.warning("PromptManager or Sampler not initialized.")
            await self.stop()
            return
        prompt = self.prompt_manager._prompts.get("summarize_text")
        if not prompt:
            self.logger.warning("Prompt 'summarize_text' not found.")
            await self.stop()
            return
        # Render the prompt (simulate input)
        rendered = prompt.content.template.replace("{{text_to_summarize}}", "This is a test.")
        self.logger.info(f"Rendered prompt: {rendered}")
        # Simulate sampling (mocked)
        self.logger.info(f"Sampling with params: {self.sampler.params.to_dict()}")
        # In a real agent, you would call: await self.sampler.sample(...)
        await asyncio.sleep(0.1)
        self.logger.info("Sampled response: <mocked response>")
        await self.stop()

    async def shutdown(self) -> None:
        self.logger.info("Shutting down PromptSamplingAgent")
