"""MCP integration for prompt management.

This module provides integration with the Model Context Protocol (MCP),
allowing OpenMAS prompts to be used with MCP services.
"""

from typing import Any, Callable, Coroutine, Dict, List, Optional

from openmas.logging import get_logger
from openmas.prompt.base import PromptManager

# Configure logging
logger = get_logger(__name__)

# Check if MCP is available
try:
    from mcp.server.fastmcp import Context

    # Import the right classes from the new SDK
    from mcp.server.fastmcp.fastmcp import PromptConfiguration, PromptRegistry

    HAS_MCP = True
except ImportError:
    logger.warning("MCP is not installed. McpPromptManager will have limited functionality.")
    HAS_MCP = False

    # Define placeholder classes to avoid type errors
    class PromptConfiguration:  # type: ignore
        """Placeholder for MCP PromptConfiguration."""

        pass

    class PromptRegistry:  # type: ignore
        """Placeholder for MCP PromptRegistry."""

        pass

    class Context:  # type: ignore
        """Placeholder for MCP Context."""

        props: Dict[str, Any]


class McpPromptManager:
    """MCP integration for prompt management.

    This class provides integration with the Model Context Protocol (MCP),
    allowing OpenMAS prompts to be used with MCP services.
    """

    def __init__(self, prompt_manager: PromptManager) -> None:
        """Initialize the MCP prompt manager.

        Args:
            prompt_manager: The underlying prompt manager to use
        """
        self.prompt_manager = prompt_manager

    async def register_all_prompts_with_server(self, server: Any, tag: Optional[str] = None) -> List[str]:
        """Register all prompts with an MCP server.

        Args:
            server: The MCP server to register prompts with
            tag: Optional tag to filter prompts by

        Returns:
            List of registered prompt names
        """
        if not HAS_MCP:
            logger.warning("MCP is not installed. Cannot register prompts with server.")
            return []

        # Check if the server supports registering prompts
        if not hasattr(server, "register_prompt") or not callable(getattr(server, "register_prompt")):
            logger.warning("Server does not support registering prompts.")
            return []

        # Get all available prompts
        prompt_metadatas = await self.prompt_manager.list_prompts(tag)
        registered_prompt_names = []

        # Register each prompt with the server
        for metadata in prompt_metadatas:
            # Load the prompt
            prompt = await self.prompt_manager.get_prompt_by_name(metadata.name)
            if not prompt:
                logger.warning(f"Could not load prompt {metadata.name}")
                continue

            # Create MCP prompt configuration
            prompt_config = PromptConfiguration(
                name=metadata.name,
                system_prompt=prompt.content.system or "",
                description=metadata.description or "",
                default_context={},
            )

            # Register the prompt with the server
            try:
                # Server API might vary, so we try to handle different cases
                if hasattr(server, "register_prompt"):
                    result = await server.register_prompt(prompt_config)
                    if result:
                        registered_prompt_names.append(metadata.name)
                        logger.info(f"Registered prompt {metadata.name} with MCP server")
                    else:
                        logger.warning(f"Failed to register prompt {metadata.name} with MCP server")
            except Exception as e:
                logger.error(f"Error registering prompt {metadata.name}: {str(e)}")

        return registered_prompt_names

    async def create_prompt_handler(
        self, prompt_name: str, system_prompt_override: Optional[str] = None
    ) -> Optional[Callable[[Any], Coroutine[Any, Any, str]]]:
        """Create a handler function for an MCP prompt.

        Args:
            prompt_name: The name of the prompt to use
            system_prompt_override: Optional override for the system prompt

        Returns:
            An async function that can be used as an MCP prompt handler
        """
        if not HAS_MCP:
            logger.warning("MCP is not installed. Cannot create prompt handler.")
            return None

        async def prompt_handler(context: Any) -> str:
            """Handle a prompt request.

            Args:
                context: The MCP context

            Returns:
                The rendered prompt
            """
            # Get the prompt
            prompt = await self.prompt_manager.get_prompt_by_name(prompt_name)
            if not prompt:
                return "Prompt not found"

            # Extract context variables
            context_vars = {}
            if hasattr(context, "props"):
                # Context comes from MCP
                for key in context.props:
                    context_vars[key] = context.props[key]

            # Render the prompt
            result = await self.prompt_manager.render_prompt(
                prompt_id=prompt.id,
                context=context_vars,
                system_override=system_prompt_override,
            )

            if not result:
                return "Error rendering prompt"

            # Return the system prompt or content
            if "system" in result and result["system"]:
                return str(result["system"])
            elif "content" in result and result["content"]:
                return str(result["content"])
            return "No content available"

        return prompt_handler
