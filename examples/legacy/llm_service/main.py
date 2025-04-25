"""Simple LLM service using FastMCP."""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

from mcp.messages import Message, MessageRole, TextContent
from mcp.server.fastmcp import Context, FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("llm_service")


# Initialize the FastMCP server
mcp = FastMCP(
    name="SimpleLLMService",
    instructions="A simple LLM service for demonstration purposes.",
)


# Define tools
@mcp.tool(description="Generate text based on a prompt")
async def generate_text(prompt: str, ctx: Context) -> str:
    """Generate text based on a prompt.

    Args:
        prompt: The prompt to generate text for
        ctx: MCP context

    Returns:
        The generated text
    """
    logger.info(f"Generating text for prompt: {prompt}")

    # In a real implementation, this would call an LLM API
    # For demonstration, we'll just return a simple response
    await ctx.info(f"Processing prompt: {prompt}")
    await ctx.report_progress(10, 100)

    await asyncio.sleep(1)  # Simulate processing time
    await ctx.report_progress(50, 100)

    response = f"This is a response to: '{prompt}'\n\nThe current time is {datetime.now()}"

    await asyncio.sleep(0.5)  # Simulate more processing
    await ctx.report_progress(100, 100)

    return response


@mcp.tool(description="Analyze the sentiment of text")
async def analyze_sentiment(text: str, ctx: Context) -> Dict[str, Any]:
    """Analyze the sentiment of text.

    Args:
        text: The text to analyze
        ctx: MCP context

    Returns:
        A dictionary with sentiment analysis results
    """
    logger.info(f"Analyzing sentiment for text: {text}")

    await ctx.info(f"Analyzing sentiment of: {text}")
    await ctx.report_progress(50, 100)

    # Simple sentiment analysis based on keywords
    positive_words = ["good", "great", "excellent", "happy", "positive"]
    negative_words = ["bad", "terrible", "sad", "negative", "awful"]

    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)

    if positive_count > negative_count:
        sentiment = "positive"
        confidence = 0.5 + (0.5 * (positive_count / (positive_count + negative_count)))
    elif negative_count > positive_count:
        sentiment = "negative"
        confidence = 0.5 + (0.5 * (negative_count / (positive_count + negative_count)))
    else:
        sentiment = "neutral"
        confidence = 0.5

    await ctx.report_progress(100, 100)

    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "positive_words": positive_count,
        "negative_words": negative_count,
    }


# Define prompts
@mcp.prompt(description="A simple question-answering prompt")
async def simple_question(question: str) -> List[Message]:
    """Create a simple question-answering prompt.

    Args:
        question: The question to answer

    Returns:
        A list of messages forming the prompt
    """
    logger.info(f"Creating prompt for question: {question}")

    return [
        Message(role=MessageRole.SYSTEM, content=[TextContent(text="You are a helpful assistant.")]),
        Message(role=MessageRole.USER, content=[TextContent(text=question)]),
    ]


@mcp.prompt(description="Create a chat history with system instructions")
async def chat_history(system_prompt: str, messages: List[Dict[str, str]]) -> List[Message]:
    """Create a prompt with a chat history.

    Args:
        system_prompt: The system instructions
        messages: List of user and assistant messages

    Returns:
        A list of messages forming the prompt
    """
    logger.info(f"Creating chat history prompt with {len(messages)} messages")

    result = [Message(role=MessageRole.SYSTEM, content=[TextContent(text=system_prompt)])]

    for msg in messages:
        role_str = msg.get("role", "user").lower()
        content_text = msg.get("content", "")

        if role_str == "user":
            role = MessageRole.USER
        elif role_str == "assistant":
            role = MessageRole.ASSISTANT
        else:
            logger.warning(f"Unknown role: {role_str}, defaulting to USER")
            role = MessageRole.USER

        result.append(Message(role=role, content=[TextContent(text=content_text)]))

    return result


# Define resources
@mcp.resource("resource://example", name="Example Resource", description="An example resource")
async def example_resource() -> str:
    """Provide the content for the example resource.

    Returns:
        The resource content as a string
    """
    logger.info("Reading example resource")
    return "This is an example resource."


@mcp.resource("resource://time", name="Current Time", description="Resource that returns the current time")
async def time_resource() -> str:
    """Provide the current time as a resource.

    Returns:
        The current time as a string
    """
    logger.info("Reading time resource")
    return f"The current time is: {datetime.now().isoformat()}"


@mcp.resource("resource://{name}", name="Named Resource", description="A resource that uses a parameter")
async def named_resource(name: str) -> str:
    """Provide content for a named resource.

    Args:
        name: The name parameter

    Returns:
        Content specific to the name
    """
    logger.info(f"Reading named resource with name: {name}")
    return f"Hello, {name}! This resource was generated at {datetime.now().isoformat()}"


if __name__ == "__main__":
    # Get the transport type from command line arguments or environment
    transport = "stdio"
    if len(sys.argv) > 1:
        transport = sys.argv[1]
    elif os.environ.get("MCP_TRANSPORT"):
        transport = os.environ.get("MCP_TRANSPORT")

    logger.info(f"Starting LLM service with transport: {transport}")
    mcp.run(transport)
