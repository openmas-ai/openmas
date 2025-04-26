"""Unit tests for LLM integration helpers."""

import os
import sys
from unittest import mock

import pytest

from openmas.integrations.llm import initialize_anthropic_client, initialize_llm_client, initialize_openai_client


class TestOpenAIIntegration:
    """Tests for OpenAI integration helpers."""

    @mock.patch.dict(sys.modules, {"openai": mock.MagicMock()})
    def test_initialize_openai_client_with_api_key_param(self):
        """Test initializing OpenAI client with API key as a parameter."""
        # Arrange
        api_key = "test-api-key"
        mock_client = mock.MagicMock()
        sys.modules["openai"].OpenAI.return_value = mock_client

        # Act
        client = initialize_openai_client(api_key=api_key)

        # Assert
        assert client == mock_client
        sys.modules["openai"].OpenAI.assert_called_once_with(api_key=api_key)

    @mock.patch.dict(sys.modules, {"openai": mock.MagicMock()})
    def test_initialize_openai_client_with_config(self):
        """Test initializing OpenAI client with config dictionary."""
        # Arrange
        config = {"openai_api_key": "config-api-key"}
        mock_client = mock.MagicMock()
        sys.modules["openai"].OpenAI.return_value = mock_client

        # Act
        client = initialize_openai_client(config=config)

        # Assert
        assert client == mock_client
        sys.modules["openai"].OpenAI.assert_called_once_with(api_key=config["openai_api_key"])

    @mock.patch.dict(sys.modules, {"openai": mock.MagicMock()})
    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "env-api-key"})
    def test_initialize_openai_client_with_env_var(self):
        """Test initializing OpenAI client with environment variable."""
        # Arrange
        mock_client = mock.MagicMock()
        sys.modules["openai"].OpenAI.return_value = mock_client

        # Act
        client = initialize_openai_client()

        # Assert
        assert client == mock_client
        sys.modules["openai"].OpenAI.assert_called_once_with(api_key="env-api-key")

    @mock.patch.dict(sys.modules, {"openai": mock.MagicMock()})
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_initialize_openai_client_no_api_key(self):
        """Test that ValueError is raised when no API key is provided."""
        # Act & Assert
        with pytest.raises(ValueError, match="No OpenAI API key provided"):
            initialize_openai_client()

    @mock.patch.dict(sys.modules, {"openai": None})
    def test_initialize_openai_client_import_error(self):
        """Test that ImportError is raised when openai package is not installed."""
        # Act & Assert
        with pytest.raises(ImportError, match="OpenAI package not installed"):
            initialize_openai_client(api_key="test")


class TestAnthropicIntegration:
    """Tests for Anthropic integration helpers."""

    @mock.patch.dict(sys.modules, {"anthropic": mock.MagicMock()})
    def test_initialize_anthropic_client_with_api_key_param(self):
        """Test initializing Anthropic client with API key as a parameter."""
        # Arrange
        api_key = "test-api-key"
        mock_client = mock.MagicMock()
        sys.modules["anthropic"].Anthropic.return_value = mock_client

        # Act
        client = initialize_anthropic_client(api_key=api_key)

        # Assert
        assert client == mock_client
        sys.modules["anthropic"].Anthropic.assert_called_once_with(api_key=api_key)

    @mock.patch.dict(sys.modules, {"anthropic": mock.MagicMock()})
    def test_initialize_anthropic_client_with_config(self):
        """Test initializing Anthropic client with config dictionary."""
        # Arrange
        config = {"anthropic_api_key": "config-api-key"}
        mock_client = mock.MagicMock()
        sys.modules["anthropic"].Anthropic.return_value = mock_client

        # Act
        client = initialize_anthropic_client(config=config)

        # Assert
        assert client == mock_client
        sys.modules["anthropic"].Anthropic.assert_called_once_with(api_key=config["anthropic_api_key"])

    @mock.patch.dict(sys.modules, {"anthropic": mock.MagicMock()})
    @mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-api-key"})
    def test_initialize_anthropic_client_with_env_var(self):
        """Test initializing Anthropic client with environment variable."""
        # Arrange
        mock_client = mock.MagicMock()
        sys.modules["anthropic"].Anthropic.return_value = mock_client

        # Act
        result = initialize_anthropic_client()

        # Assert
        assert result == mock_client
        sys.modules["anthropic"].Anthropic.assert_called_once_with(api_key="env-api-key")

    @mock.patch.dict(sys.modules, {"anthropic": mock.MagicMock()})
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_initialize_anthropic_client_no_api_key(self):
        """Test that ValueError is raised when no API key is provided."""
        # Act & Assert
        with pytest.raises(ValueError, match="No Anthropic API key provided"):
            initialize_anthropic_client()

    @mock.patch.dict(sys.modules, {"anthropic": None})
    def test_initialize_anthropic_client_import_error(self):
        """Test that ImportError is raised when anthropic package is not installed."""
        # Act & Assert
        with pytest.raises(ImportError, match="Anthropic package not installed"):
            initialize_anthropic_client(api_key="test")


class TestGoogleIntegration:
    """Tests for Google GenerativeAI integration helpers."""

    def test_initialize_google_genai_with_api_key_param(self, monkeypatch):
        """Test initializing Google GenerativeAI with API key as a parameter."""
        # Setup comprehensive google module mocking
        mock_genai = mock.MagicMock()
        mock_model = mock.MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        # Create a mock google module
        mock_google = mock.MagicMock()
        mock_google.generativeai = mock_genai

        # Patch sys.modules before importing the function
        monkeypatch.setitem(sys.modules, "google", mock_google)
        monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # API key for test
        api_key = "test-api-key"

        # Act
        result = initialize_google_genai(api_key=api_key)

        # Assert
        mock_genai.configure.assert_called_once_with(api_key=api_key)
        mock_genai.GenerativeModel.assert_called_once_with("gemini-pro")
        assert result == mock_model

    def test_initialize_google_genai_with_config(self, monkeypatch):
        """Test initializing Google GenerativeAI with config dictionary."""
        # Setup google.generativeai module mocking
        mock_genai = mock.MagicMock()
        mock_model = mock.MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        # Create a mock google module
        mock_google = mock.MagicMock()
        mock_google.generativeai = mock_genai

        # Patch sys.modules before importing the function
        monkeypatch.setitem(sys.modules, "google", mock_google)
        monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # Config with API key
        config = {"google_api_key": "config-api-key"}

        # Act
        result = initialize_google_genai(config=config)

        # Assert
        mock_genai.configure.assert_called_once_with(api_key=config["google_api_key"])
        mock_genai.GenerativeModel.assert_called_once_with("gemini-pro")
        assert result == mock_model

    def test_initialize_google_genai_with_env_var(self, monkeypatch):
        """Test initializing Google GenerativeAI with environment variables."""
        # Setup google.generativeai module mocking
        mock_genai = mock.MagicMock()
        mock_model = mock.MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        # Create a mock google module
        mock_google = mock.MagicMock()
        mock_google.generativeai = mock_genai

        # Patch sys.modules before importing the function
        monkeypatch.setitem(sys.modules, "google", mock_google)
        monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)

        # Set environment variables
        monkeypatch.setenv("GOOGLE_API_KEY", "env-api-key")
        monkeypatch.setenv("GOOGLE_MODEL_NAME", "custom-model")

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # Act
        result = initialize_google_genai()

        # Assert
        mock_genai.configure.assert_called_once_with(api_key="env-api-key")
        mock_genai.GenerativeModel.assert_called_once_with("custom-model")
        assert result == mock_model

    def test_initialize_google_genai_no_api_key(self, monkeypatch):
        """Test that ValueError is raised when no API key is provided."""
        # Setup google.generativeai module mocking
        mock_genai = mock.MagicMock()

        # Create a mock google module
        mock_google = mock.MagicMock()
        mock_google.generativeai = mock_genai

        # Patch sys.modules before importing the function
        monkeypatch.setitem(sys.modules, "google", mock_google)
        monkeypatch.setitem(sys.modules, "google.generativeai", mock_genai)

        # Clear environment variables
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # Act & Assert
        with pytest.raises(ValueError, match="No Google API key provided"):
            initialize_google_genai()

    def test_initialize_google_genai_import_error(self, monkeypatch):
        """Test that ImportError is raised when generativeai package is not installed."""
        # Remove the google module from sys.modules to cause an import error
        monkeypatch.delitem(sys.modules, "google", raising=False)

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # Act & Assert
        with pytest.raises(ImportError, match="Google GenerativeAI package not installed"):
            initialize_google_genai(api_key="test")


class TestLLMClientInitializer:
    """Tests for the generic LLM client initializer."""

    @mock.patch("openmas.integrations.llm.initialize_openai_client")
    def test_initialize_llm_client_openai(self, mock_init_openai):
        """Test initializing LLM client with OpenAI provider."""
        # Arrange
        config = {"key": "value"}
        api_key = "test-api-key"
        model = "gpt-4"
        mock_client = mock.MagicMock()
        mock_init_openai.return_value = mock_client

        # Act
        result = initialize_llm_client("openai", config, api_key, model)

        # Assert
        assert result == mock_client
        mock_init_openai.assert_called_once_with(config, api_key, model)

    @mock.patch("openmas.integrations.llm.initialize_anthropic_client")
    def test_initialize_llm_client_anthropic(self, mock_init_anthropic):
        """Test initializing LLM client with Anthropic provider."""
        # Arrange
        config = {"key": "value"}
        api_key = "test-api-key"
        model = "claude-3"
        mock_client = mock.MagicMock()
        mock_init_anthropic.return_value = mock_client

        # Act
        result = initialize_llm_client("anthropic", config, api_key, model)

        # Assert
        assert result == mock_client
        mock_init_anthropic.assert_called_once_with(config, api_key, model)

    @mock.patch("openmas.integrations.llm.initialize_google_genai")
    def test_initialize_llm_client_google(self, mock_init_google):
        """Test initializing LLM client with Google provider."""
        # Arrange
        config = {"key": "value"}
        api_key = "test-api-key"
        model = "gemini-pro"
        mock_client = mock.MagicMock()
        mock_init_google.return_value = mock_client

        # Act
        result = initialize_llm_client("google", config, api_key, model)

        # Assert
        assert result == mock_client
        mock_init_google.assert_called_once_with(config, api_key, model)

    def test_initialize_llm_client_unsupported_provider(self):
        """Test that ValueError is raised for unsupported provider."""
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported LLM provider: unknown"):
            initialize_llm_client("unknown")
