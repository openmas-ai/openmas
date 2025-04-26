"""Unit tests for LLM integration helpers."""

import sys
from unittest import mock

import pytest

from openmas.integrations.llm import initialize_anthropic_client, initialize_llm_client, initialize_openai_client


class TestOpenAIIntegration:
    """Tests for OpenAI integration helpers."""

    def test_initialize_openai_client_with_api_key_param(self, mock_openai):
        """Test initializing OpenAI client with API key as a parameter."""
        # Arrange
        mock_module, mock_client = mock_openai
        api_key = "test-api-key"

        # Act
        client = initialize_openai_client(api_key=api_key)

        # Assert
        assert client == mock_client
        mock_module.OpenAI.assert_called_once_with(api_key=api_key)

    def test_initialize_openai_client_with_config(self, mock_openai):
        """Test initializing OpenAI client with config dictionary."""
        # Arrange
        mock_module, mock_client = mock_openai
        config = {"openai_api_key": "config-api-key"}

        # Act
        client = initialize_openai_client(config=config)

        # Assert
        assert client == mock_client
        mock_module.OpenAI.assert_called_once_with(api_key=config["openai_api_key"])

    def test_initialize_openai_client_with_env_var(self, mock_openai, mock_env_vars):
        """Test initializing OpenAI client with environment variable."""
        # Arrange
        mock_module, mock_client = mock_openai

        # Ensure env var is set
        mock_env_vars["set"]("OPENAI_API_KEY", "env-api-key")

        # Act
        client = initialize_openai_client()

        # Assert
        assert client == mock_client
        mock_module.OpenAI.assert_called_once_with(api_key="env-api-key")

    def test_initialize_openai_client_no_api_key(self, mock_env_vars):
        """Test that ValueError is raised when no API key is provided."""
        # Clear any existing API key in the environment
        mock_env_vars["clear"]("OPENAI_API_KEY")

        # Mock openai module but with no API key provided
        with mock.patch.dict(sys.modules, {"openai": mock.MagicMock()}):
            # Act & Assert
            with pytest.raises(ValueError, match="No OpenAI API key provided"):
                initialize_openai_client()

    def test_initialize_openai_client_import_error(self):
        """Test that ImportError is raised when openai package is not installed."""
        # Set openai module to None to simulate import error
        with mock.patch.dict(sys.modules, {"openai": None}):
            # Act & Assert
            with pytest.raises(ImportError, match="OpenAI package not installed"):
                initialize_openai_client(api_key="test")


class TestAnthropicIntegration:
    """Tests for Anthropic integration helpers."""

    def test_initialize_anthropic_client_with_api_key_param(self, mock_anthropic):
        """Test initializing Anthropic client with API key as a parameter."""
        # Arrange
        mock_module, mock_client = mock_anthropic
        api_key = "test-api-key"

        # Act
        client = initialize_anthropic_client(api_key=api_key)

        # Assert
        assert client == mock_client
        mock_module.Anthropic.assert_called_once_with(api_key=api_key)

    def test_initialize_anthropic_client_with_config(self, mock_anthropic):
        """Test initializing Anthropic client with config dictionary."""
        # Arrange
        mock_module, mock_client = mock_anthropic
        config = {"anthropic_api_key": "config-api-key"}

        # Act
        client = initialize_anthropic_client(config=config)

        # Assert
        assert client == mock_client
        mock_module.Anthropic.assert_called_once_with(api_key=config["anthropic_api_key"])

    def test_initialize_anthropic_client_with_env_var(self, mock_anthropic, mock_env_vars):
        """Test initializing Anthropic client with environment variable."""
        # Arrange
        mock_module, mock_client = mock_anthropic

        # Ensure env var is set
        mock_env_vars["set"]("ANTHROPIC_API_KEY", "env-api-key")

        # Act
        result = initialize_anthropic_client()

        # Assert
        assert result == mock_client
        mock_module.Anthropic.assert_called_once_with(api_key="env-api-key")

    def test_initialize_anthropic_client_no_api_key(self, mock_env_vars):
        """Test that ValueError is raised when no API key is provided."""
        # Clear any existing API key in the environment
        mock_env_vars["clear"]("ANTHROPIC_API_KEY")

        # Mock anthropic module but with no API key provided
        with mock.patch.dict(sys.modules, {"anthropic": mock.MagicMock()}):
            # Act & Assert
            with pytest.raises(ValueError, match="No Anthropic API key provided"):
                initialize_anthropic_client()

    def test_initialize_anthropic_client_import_error(self):
        """Test that ImportError is raised when anthropic package is not installed."""
        # Set anthropic module to None to simulate import error
        with mock.patch.dict(sys.modules, {"anthropic": None}):
            # Act & Assert
            with pytest.raises(ImportError, match="Anthropic package not installed"):
                initialize_anthropic_client(api_key="test")


class TestGoogleIntegration:
    """Tests for Google GenerativeAI integration helpers."""

    def test_initialize_google_genai_with_api_key_param(self, mock_google_genai):
        """Test initializing Google GenerativeAI with API key as a parameter."""
        # Arrange
        mock_genai, mock_model = mock_google_genai
        api_key = "test-api-key"

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # Act
        result = initialize_google_genai(api_key=api_key)

        # Assert
        mock_genai.configure.assert_called_once_with(api_key=api_key)
        mock_genai.GenerativeModel.assert_called_once_with("gemini-pro")
        assert result == mock_model

    def test_initialize_google_genai_with_config(self, mock_google_genai):
        """Test initializing Google GenerativeAI with config dictionary."""
        # Arrange
        mock_genai, mock_model = mock_google_genai
        config = {"google_api_key": "config-api-key"}

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # Act
        result = initialize_google_genai(config=config)

        # Assert
        mock_genai.configure.assert_called_once_with(api_key=config["google_api_key"])
        mock_genai.GenerativeModel.assert_called_once_with("gemini-pro")
        assert result == mock_model

    def test_initialize_google_genai_with_env_var(self, mock_google_genai, mock_env_vars):
        """Test initializing Google GenerativeAI with environment variable."""
        # Arrange
        mock_genai, mock_model = mock_google_genai

        # Ensure env var is set
        mock_env_vars["set"]("GOOGLE_API_KEY", "env-api-key")

        # Import the function after patching
        from openmas.integrations.llm import initialize_google_genai

        # Act
        result = initialize_google_genai()

        # Assert
        mock_genai.configure.assert_called_once_with(api_key="env-api-key")
        mock_genai.GenerativeModel.assert_called_once_with("gemini-pro")
        assert result == mock_model

    def test_initialize_google_genai_no_api_key(self, mock_env_vars):
        """Test that ValueError is raised when no API key is provided."""
        # Clear any existing API key in the environment
        mock_env_vars["clear"]("GOOGLE_API_KEY")

        # Create mock Google module
        mock_genai = mock.MagicMock()
        mock_google = mock.MagicMock()
        mock_google.generativeai = mock_genai

        # Mock Google modules but with no API key provided
        with mock.patch.dict(sys.modules, {"google": mock_google, "google.generativeai": mock_genai}):
            # Import the function after patching
            from openmas.integrations.llm import initialize_google_genai

            # Act & Assert
            with pytest.raises(ValueError, match="No Google API key provided"):
                initialize_google_genai()

    def test_initialize_google_genai_import_error(self):
        """Test that ImportError is raised when Google package is not installed."""
        # Set google module to None to simulate import error
        with mock.patch.dict(sys.modules, {"google": None}):
            # Import the function after patching (with the import error)
            with pytest.raises(ImportError):
                from openmas.integrations.llm import initialize_google_genai

                # This should not execute, but if it does, it would raise another error
                initialize_google_genai(api_key="test")


class TestLLMClientInitializer:
    """Tests for the initialize_llm_client function."""

    @mock.patch("openmas.integrations.llm.initialize_openai_client")
    def test_initialize_llm_client_openai(self, mock_init_openai, mock_env_vars):
        """Test initialize_llm_client with OpenAI provider."""
        # Arrange
        api_key = "test-api-key"
        mock_client = mock.MagicMock()
        mock_init_openai.return_value = mock_client

        # Act
        result = initialize_llm_client("openai", api_key=api_key)

        # Assert
        assert result == mock_client
        mock_init_openai.assert_called_once_with(None, api_key, None)

    @mock.patch("openmas.integrations.llm.initialize_anthropic_client")
    def test_initialize_llm_client_anthropic(self, mock_init_anthropic, mock_env_vars):
        """Test initialize_llm_client with Anthropic provider."""
        # Arrange
        api_key = "test-api-key"
        mock_client = mock.MagicMock()
        mock_init_anthropic.return_value = mock_client

        # Act
        result = initialize_llm_client("anthropic", api_key=api_key)

        # Assert
        assert result == mock_client
        mock_init_anthropic.assert_called_once_with(None, api_key, None)

    @mock.patch("openmas.integrations.llm.initialize_google_genai")
    def test_initialize_llm_client_google(self, mock_init_google, mock_env_vars):
        """Test initialize_llm_client with Google provider."""
        # Arrange
        api_key = "test-api-key"
        mock_client = mock.MagicMock()
        mock_init_google.return_value = mock_client

        # Act
        result = initialize_llm_client("google", api_key=api_key)

        # Assert
        assert result == mock_client
        mock_init_google.assert_called_once_with(None, api_key, None)

    def test_initialize_llm_client_unsupported_provider(self):
        """Test initialize_llm_client with an unsupported provider."""
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            initialize_llm_client("unsupported_provider", api_key="test")
