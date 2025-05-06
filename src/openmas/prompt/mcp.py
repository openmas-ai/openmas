"""MCP integration for prompt management.

This module provides integration between the OpenMAS prompt management system
and the MCP protocol, allowing prompts to be exposed as MCP resources.
"""

from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

from openmas.logging import get_logger
from openmas.prompt.base import Prompt, PromptManager

# Configure logging
logger = get_logger(__name__)

# Check if MCP is installed
try:
    from mcp.server.prompts import Prompt as McpPrompt
    
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    
    # Define dummy class for type checking
    class McpPrompt:
        def __init__(self, fn: Any = None, name: str = "", description: str = ""):
            pass


class McpPromptManager:
    """Manages prompts for MCP integration.
    
    This class wraps a PromptManager and provides methods for registering
    prompts with an MCP server.
    """
    
    def __init__(self, prompt_manager: PromptManager) -> None:
        """Initialize the MCP prompt manager.
        
        Args:
            prompt_manager: The prompt manager to wrap
        """
        self.prompt_manager = prompt_manager
        
        if not HAS_MCP:
            logger.warning("MCP is not installed. McpPromptManager will have limited functionality.")
    
    async def register_prompt_with_server(
        self,
        prompt_id: str,
        server: Any,
        name: Optional[str] = None,
    ) -> Optional[str]:
        """Register a prompt with an MCP server.
        
        Args:
            prompt_id: The ID of the prompt to register
            server: The MCP server to register with
            name: Optional name for the prompt (defaults to the prompt's name)
            
        Returns:
            The name of the registered prompt, or None if registration failed
        """
        if not HAS_MCP:
            logger.error("Cannot register prompt with MCP server: MCP is not installed")
            return None
            
        # Get the prompt from the manager
        prompt = await self.prompt_manager.get_prompt(prompt_id)
        if not prompt:
            logger.error(f"Cannot register prompt with MCP server: Prompt {prompt_id} not found")
            return None
            
        # Use the provided name or the prompt's name
        prompt_name = name or prompt.metadata.name
        
        # Create a handler function for the prompt
        async def prompt_handler(**kwargs: Any) -> str:
            # Render the prompt with the provided arguments
            rendered = await self.prompt_manager.render_prompt(prompt_id, context=kwargs)
            if not rendered:
                return f"Error: Prompt {prompt_id} not found or could not be rendered"
                
            # Return the rendered content
            if rendered.get("system") and rendered.get("content"):
                return f"{rendered['system']}\n\n{rendered['content']}"
            return rendered.get("content", "")
        
        # Register the prompt with the server
        if hasattr(server, "register_prompt"):
            try:
                # Create an MCP prompt
                mcp_prompt = McpPrompt(
                    fn=prompt_handler,
                    name=prompt_name,
                    description=prompt.metadata.description or f"Prompt: {prompt_name}",
                )
                
                # Register the prompt with the server
                await server.register_prompt(prompt_name, mcp_prompt)
                logger.debug(f"Registered prompt {prompt_name} with MCP server")
                return prompt_name
            except Exception as e:
                logger.error(f"Error registering prompt {prompt_name} with MCP server: {e}")
                return None
        else:
            logger.error(f"Cannot register prompt with MCP server: Server does not support register_prompt")
            return None

    async def register_all_prompts_with_server(
        self,
        server: Any,
        tag: Optional[str] = None,
    ) -> List[str]:
        """Register all prompts with an MCP server.
        
        Args:
            server: The MCP server to register with
            tag: Optional tag to filter prompts
            
        Returns:
            List of names of registered prompts
        """
        if not HAS_MCP:
            logger.error("Cannot register prompts with MCP server: MCP is not installed")
            return []
            
        # Get all prompts from the manager
        prompt_metadata_list = await self.prompt_manager.list_prompts(tag=tag)
        
        # Register each prompt
        registered_names = []
        for metadata in prompt_metadata_list:
            # Get the prompt by name
            prompt = await self.prompt_manager.get_prompt_by_name(metadata.name)
            if prompt:
                name = await self.register_prompt_with_server(prompt.id, server)
                if name:
                    registered_names.append(name)
        
        return registered_names 