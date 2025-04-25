"""LLM integration helpers for OpenMAS.

This module provides helper functions for integrating Large Language Models
(LLMs) into OpenMAS agents.
"""

import os
from typing import Any, Dict, Optional

from openmas.logging import get_logger

logger = get_logger(__name__)


def initialize_openai_client(
    config: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Any:
    """Initialize an OpenAI client.

    Args:
        config: Optional configuration dictionary that may contain openai_api_key
        api_key: Optional API key (overrides config)
        model: Optional model name

    Returns:
        The initialized OpenAI client

    Raises:
        ImportError: If the openai package is not installed
        ValueError: If no API key is provided or found in environment variables
    """
    try:
        import openai  # type: ignore
    except ImportError:
        error_msg = "OpenAI package not installed. Install with: pip install openai"
        logger.error(error_msg)
        raise ImportError(error_msg)

    # Get API key from (in order of precedence):
    # 1. api_key parameter
    # 2. config dictionary
    # 3. OPENAI_API_KEY environment variable
    effective_api_key = api_key
    if effective_api_key is None and config is not None:
        effective_api_key = config.get("openai_api_key")
    if effective_api_key is None:
        effective_api_key = os.environ.get("OPENAI_API_KEY")

    if effective_api_key is None:
        error_msg = (
            "No OpenAI API key provided. " "Set the OPENAI_API_KEY environment variable or provide it in the config."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Initialize the client
    client = openai.OpenAI(api_key=effective_api_key)

    # Log info (but don't include the API key)
    model_info = model or os.environ.get("OPENAI_MODEL_NAME", "gpt-4")
    logger.info("OpenAI client initialized", model=model_info)

    return client


def initialize_anthropic_client(
    config: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Any:
    """Initialize an Anthropic client.

    Args:
        config: Optional configuration dictionary that may contain anthropic_api_key
        api_key: Optional API key (overrides config)
        model: Optional model name

    Returns:
        The initialized Anthropic client

    Raises:
        ImportError: If the anthropic package is not installed
        ValueError: If no API key is provided or found in environment variables
    """
    try:
        import anthropic  # type: ignore
    except ImportError:
        error_msg = "Anthropic package not installed. Install with: pip install anthropic"
        logger.error(error_msg)
        raise ImportError(error_msg)

    # Get API key from (in order of precedence):
    # 1. api_key parameter
    # 2. config dictionary
    # 3. ANTHROPIC_API_KEY environment variable
    effective_api_key = api_key
    if effective_api_key is None and config is not None:
        effective_api_key = config.get("anthropic_api_key")
    if effective_api_key is None:
        effective_api_key = os.environ.get("ANTHROPIC_API_KEY")

    if effective_api_key is None:
        error_msg = (
            "No Anthropic API key provided. "
            "Set the ANTHROPIC_API_KEY environment variable or provide it in the config."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Initialize the client
    client = anthropic.Anthropic(api_key=effective_api_key)

    # Log info (but don't include the API key)
    model_info = model or os.environ.get("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")
    logger.info("Anthropic client initialized", model=model_info)

    return client


def initialize_google_genai(
    config: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Any:
    """Initialize Google's Generative AI client.

    Args:
        config: Optional configuration dictionary that may contain google_api_key
        api_key: Optional API key (overrides config)
        model: Optional model name to use

    Returns:
        A GenerativeModel instance for the specified or default model

    Raises:
        ImportError: If the google-generativeai package is not installed
        ValueError: If no API key is provided or found in environment variables
    """
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        error_msg = "Google GenerativeAI package not installed. Install with: pip install google-generativeai"
        logger.error(error_msg)
        raise ImportError(error_msg)

    # Get API key from (in order of precedence):
    # 1. api_key parameter
    # 2. config dictionary
    # 3. GOOGLE_API_KEY environment variable
    effective_api_key = api_key
    if effective_api_key is None and config is not None:
        effective_api_key = config.get("google_api_key")
    if effective_api_key is None:
        effective_api_key = os.environ.get("GOOGLE_API_KEY")

    if effective_api_key is None:
        error_msg = (
            "No Google API key provided. " "Set the GOOGLE_API_KEY environment variable or provide it in the config."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Configure the client
    genai.configure(api_key=effective_api_key)

    # Get the model name
    model_name = model or os.environ.get("GOOGLE_MODEL_NAME", "gemini-pro")

    # Initialize and return the model
    model_instance = genai.GenerativeModel(model_name)
    logger.info("Google GenerativeAI client initialized", model=model_name)

    return model_instance


def initialize_llm_client(
    provider: str,
    config: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Any:
    """Initialize an LLM client based on the specified provider.

    Args:
        provider: The LLM provider to use ("openai", "anthropic", or "google")
        config: Optional configuration dictionary
        api_key: Optional API key (overrides config)
        model: Optional model name

    Returns:
        The initialized LLM client

    Raises:
        ValueError: If the provider is not supported
    """
    provider = provider.lower()

    if provider == "openai":
        return initialize_openai_client(config, api_key, model)
    elif provider == "anthropic":
        return initialize_anthropic_client(config, api_key, model)
    elif provider == "google":
        return initialize_google_genai(config, api_key, model)
    else:
        supported = ["openai", "anthropic", "google"]
        error_msg = f"Unsupported LLM provider: {provider}. Supported providers: {', '.join(supported)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
