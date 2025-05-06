"""Enhanced MCP agent with prompt management and sampling capabilities.

This module extends the base McpAgent to provide integrated prompt management
and sampling capabilities, making it easier to develop agents that use LLMs.
"""

from typing import Any, Dict, List, Optional, Set, Type, Union, cast

from openmas.agent.mcp import McpAgent
from openmas.logging import get_logger
from openmas.prompt import Prompt, PromptManager
from openmas.prompt.mcp import McpPromptManager
from openmas.sampling import (
    MessageRole,
    SamplingParameters,
    SamplingResult,
)
from openmas.sampling.providers.mcp import McpAgentSampler

# Configure logging
logger = get_logger(__name__)


class PromptMcpAgent(McpAgent):
    """Enhanced MCP agent with prompt management and sampling capabilities.
    
    This agent extends the base McpAgent to provide integrated prompt management
    and sampling capabilities, making it easier to develop agents that use LLMs.
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        prompt_manager: Optional[PromptManager] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the enhanced MCP agent.
        
        Args:
            name: Optional name for the agent
            config: Optional configuration for the agent
            prompt_manager: Optional prompt manager to use
            **kwargs: Additional keyword arguments for the parent class
        """
        super().__init__(name, config, **kwargs)
        
        # Set up prompt management
        self.prompt_manager = prompt_manager or PromptManager()
        self.mcp_prompt_manager = McpPromptManager(self.prompt_manager)
        
        # Set up sampling
        self._sampler = None
        self._llm_service: Optional[str] = kwargs.get("llm_service")
        self._default_model: Optional[str] = kwargs.get("default_model")
    
    async def setup(self) -> None:
        """Set up the agent.
        
        This method is called during agent initialization and should be used to
        set up the agent's resources and register handlers.
        """
        await super().setup()
        
        # Create the sampler if we have an LLM service
        if self._llm_service and self.communicator:
            self._sampler = McpAgentSampler(
                agent=self,
                target_service=self._llm_service,
                default_model=self._default_model,
            )
    
    async def register_prompts_with_server(self) -> None:
        """Register prompts with the MCP server if running in server mode.
        
        This method is called during setup to register all prompts with the MCP
        server if the agent is running in server mode.
        """
        if not self._server_mode:
            return
            
        if not self.communicator:
            logger.warning("Cannot register prompts: No communicator set")
            return
            
        # Check if the communicator supports registering prompts
        if not hasattr(self.communicator, "register_prompt"):
            logger.warning(
                f"Communicator {type(self.communicator).__name__} does not support registering prompts"
            )
            return
            
        # Register all prompts with the server
        if not hasattr(self.communicator, "agent"):
            # Store a reference to this agent for registration
            setattr(self.communicator, "agent", self)
            
        # Register all prompts
        registered_names = await self.mcp_prompt_manager.register_all_prompts_with_server(
            server=self.communicator
        )
        
        if registered_names:
            logger.info(f"Registered {len(registered_names)} prompts with MCP server")
        else:
            logger.info("No prompts registered with MCP server")
    
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
        return await self.prompt_manager.create_prompt(
            name=name,
            description=description,
            system=system,
            template=template,
            examples=examples,
            tags=tags,
            author=author,
        )
    
    async def render_prompt(
        self,
        prompt_id: str,
        context: Optional[Dict[str, Any]] = None,
        system_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Render a prompt with context.
        
        Args:
            prompt_id: The ID of the prompt to render
            context: Optional context to use for rendering
            system_override: Optional system prompt override
            
        Returns:
            The rendered prompt as a dictionary with system and content fields,
            or None if the prompt was not found
        """
        return await self.prompt_manager.render_prompt(
            prompt_id=prompt_id,
            context=context,
            system_override=system_override,
        )
    
    async def sample(
        self,
        prompt_id: str,
        context: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        llm_service: Optional[str] = None,
    ) -> SamplingResult:
        """Sample from a prompt.
        
        Args:
            prompt_id: The ID of the prompt to sample from
            context: Optional context to use for template rendering
            parameters: Optional sampling parameters
            model: Optional model to use
            llm_service: Optional LLM service to use (overrides the default)
            
        Returns:
            The sampling result
            
        Raises:
            ValueError: If sampling is not available or the prompt is not found
        """
        # Check if we have a sampler
        if not self._sampler:
            if not llm_service and not self._llm_service:
                raise ValueError(
                    "No LLM service specified. Provide one during initialization or when calling sample()."
                )
                
            # Create a sampler if we have an LLM service
            target_service = llm_service or self._llm_service
            if target_service:
                self._sampler = McpAgentSampler(
                    agent=self,
                    target_service=target_service,
                    default_model=self._default_model,
                )
                
        if not self._sampler:
            raise ValueError("Sampling is not available")
            
        # Get the prompt
        prompt = await self.prompt_manager.get_prompt(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt {prompt_id} not found")
            
        # Sample from the prompt
        return await self._sampler.sample_from_prompt(
            prompt=prompt,
            context_vars=context,
            parameters=parameters,
            model=model,
        )
    
    async def sample_text(
        self,
        system: Optional[str] = None,
        prompt: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        llm_service: Optional[str] = None,
    ) -> str:
        """Sample from a text prompt.
        
        Args:
            system: Optional system prompt
            prompt: The prompt text
            parameters: Optional sampling parameters
            model: Optional model to use
            llm_service: Optional LLM service to use (overrides the default)
            
        Returns:
            The generated text
            
        Raises:
            ValueError: If sampling is not available
        """
        # Check if we have a sampler
        if not self._sampler:
            if not llm_service and not self._llm_service:
                raise ValueError(
                    "No LLM service specified. Provide one during initialization or when calling sample_text()."
                )
                
            # Create a sampler if we have an LLM service
            target_service = llm_service or self._llm_service
            if target_service:
                self._sampler = McpAgentSampler(
                    agent=self,
                    target_service=target_service,
                    default_model=self._default_model,
                )
                
        if not self._sampler:
            raise ValueError("Sampling is not available")
            
        # Create a sampling context
        context = self._sampler.create_context(
            system=system,
            messages=[{"role": MessageRole.USER, "content": prompt}],
            parameters=parameters,
        )
        
        # Sample from the context
        result = await self._sampler.sample(context, model)
        return result.content
    
    async def chat(
        self,
        system: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        llm_service: Optional[str] = None,
    ) -> SamplingResult:
        """Chat with an LLM.
        
        Args:
            system: Optional system prompt
            messages: Optional list of messages
            parameters: Optional sampling parameters
            model: Optional model to use
            llm_service: Optional LLM service to use (overrides the default)
            
        Returns:
            The sampling result
            
        Raises:
            ValueError: If sampling is not available
        """
        # Check if we have a sampler
        if not self._sampler:
            if not llm_service and not self._llm_service:
                raise ValueError(
                    "No LLM service specified. Provide one during initialization or when calling chat()."
                )
                
            # Create a sampler if we have an LLM service
            target_service = llm_service or self._llm_service
            if target_service:
                self._sampler = McpAgentSampler(
                    agent=self,
                    target_service=target_service,
                    default_model=self._default_model,
                )
                
        if not self._sampler:
            raise ValueError("Sampling is not available")
            
        # Create a sampling context
        context = self._sampler.create_context(
            system=system,
            messages=messages,
            parameters=parameters,
        )
        
        # Sample from the context
        return await self._sampler.sample(context, model) 