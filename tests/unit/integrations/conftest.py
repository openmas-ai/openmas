"""Fixtures for integration tests."""

import os
import sys
from unittest import mock

import pytest


@pytest.fixture
def mock_openai():
    """Mock the OpenAI package and client.

    Returns:
        tuple: (mock_openai_module, mock_openai_client)
    """
    # Create mock OpenAI module
    mock_openai_module = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_openai_module.OpenAI.return_value = mock_client

    # Set up completion methods
    mock_completion = mock.MagicMock()
    mock_completion.choices = [mock.MagicMock(message=mock.MagicMock(content="This is a mock OpenAI response"))]
    mock_client.chat.completions.create.return_value = mock_completion

    # Apply the patch
    with mock.patch.dict(sys.modules, {"openai": mock_openai_module}):
        # Set environment variable for tests that rely on it
        original_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        yield mock_openai_module, mock_client

        # Restore environment
        if original_api_key:
            os.environ["OPENAI_API_KEY"] = original_api_key
        else:
            del os.environ["OPENAI_API_KEY"]


@pytest.fixture
def mock_anthropic():
    """Mock the Anthropic package and client.

    Returns:
        tuple: (mock_anthropic_module, mock_anthropic_client)
    """
    # Create mock Anthropic module
    mock_anthropic_module = mock.MagicMock()
    mock_client = mock.MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client

    # Set up completion methods
    mock_completion = mock.MagicMock()
    mock_completion.content = [mock.MagicMock(text="This is a mock Anthropic response")]
    mock_client.messages.create.return_value = mock_completion

    # Apply the patch
    with mock.patch.dict(sys.modules, {"anthropic": mock_anthropic_module}):
        # Set environment variable for tests that rely on it
        original_api_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

        yield mock_anthropic_module, mock_client

        # Restore environment
        if original_api_key:
            os.environ["ANTHROPIC_API_KEY"] = original_api_key
        else:
            del os.environ["ANTHROPIC_API_KEY"]


@pytest.fixture
def mock_google_genai():
    """Mock the Google GenerativeAI package and client.

    Returns:
        tuple: (mock_genai_module, mock_generation_model)
    """
    # Create mock Google module structure
    mock_genai = mock.MagicMock()
    mock_model = mock.MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    # Set up generation methods
    mock_response = mock.MagicMock()
    mock_response.text = "This is a mock Google GenerativeAI response"
    mock_model.generate_content.return_value = mock_response

    # Create mock Google module
    mock_google = mock.MagicMock()
    mock_google.generativeai = mock_genai

    # Apply the patch
    with mock.patch.dict(sys.modules, {"google": mock_google, "google.generativeai": mock_genai}):
        # Set environment variable for tests that rely on it
        original_api_key = os.environ.get("GOOGLE_API_KEY")
        os.environ["GOOGLE_API_KEY"] = "test-google-key"

        yield mock_genai, mock_model

        # Restore environment
        if original_api_key:
            os.environ["GOOGLE_API_KEY"] = original_api_key
        else:
            del os.environ["GOOGLE_API_KEY"]
