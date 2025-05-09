"""Tests for the prompts CLI commands."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from click.testing import CliRunner

from openmas.cli.prompts import SimpleTemplateRenderer, list_prompts, prompts


class TestPromptsCommands:
    """Tests for the prompts command group."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_project_config(self):
        """Create a mock project configuration with prompts."""
        return {
            "name": "test_project",
            "version": "0.1.0",
            "agents": {
                "agent1": {
                    "module": "agents.agent1",
                    "class": "Agent1",
                    "prompts": [
                        {"name": "greeting", "template": "Hello, {{name}}!", "input_variables": ["name"]},
                        {"name": "farewell", "template_file": "farewell.txt", "input_variables": ["name"]},
                    ],
                },
                "agent2": {
                    "module": "agents.agent2",
                    "class": "Agent2",
                    "prompts": [{"name": "analysis", "template": "Analyzing {{data}}...", "input_variables": ["data"]}],
                },
                "agent3": {
                    "module": "agents.agent3",
                    "class": "Agent3",
                    # No prompts defined
                },
            },
        }

    def test_prompts_list_command(self, cli_runner, mock_project_config):
        """Test the prompts list command."""
        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
        ):
            # Test directly calling the function rather than through the CLI
            result = cli_runner.invoke(list_prompts)
            assert result.exit_code == 0
            assert "agent1" in result.output
            assert "greeting" in result.output
            assert "farewell" in result.output
            assert "agent2" in result.output
            assert "analysis" in result.output
            assert "Hello, {{name}}!" in result.output
            assert "farewell.txt" in result.output
            assert "agent3" not in result.output  # agent3 has no prompts, so shouldn't be listed

    def test_prompts_list_filter_by_agent(self, cli_runner, mock_project_config):
        """Test the prompts list command with agent filter."""
        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
        ):
            # Test directly calling the function with agent parameter
            result = cli_runner.invoke(list_prompts, ["--agent", "agent1"])
            assert result.exit_code == 0
            assert "agent1" in result.output
            assert "greeting" in result.output
            assert "farewell" in result.output
            assert "agent2" not in result.output
            assert "analysis" not in result.output

    def test_prompts_list_no_project(self, cli_runner):
        """Test the prompts list command when no project is found."""
        # We need to patch Path.cwd to avoid FileNotFoundError in tests
        with (
            patch("pathlib.Path.cwd", return_value=Path("/fake/cwd")),
            patch("openmas.config._find_project_root", return_value=None),
            patch("sys.exit", side_effect=SystemExit(1)) as mock_exit,
            patch("click.echo") as mock_echo,
        ):
            # Call the function directly to avoid Click's runner that captures sys.exit
            from openmas.cli.prompts import _load_project_config

            with pytest.raises(SystemExit):
                _load_project_config()

            # Check if the correct error message was echoed
            mock_echo.assert_any_call(
                "❌ Project configuration file 'openmas_project.yml' not found in current or parent directories"
            )

            # Verify mock_exit was called
            mock_exit.assert_called_once_with(1)

    def test_prompts_list_no_prompts(self, cli_runner):
        """Test the prompts list command when no prompts are defined."""
        empty_config = {
            "name": "test_project",
            "version": "0.1.0",
            "agents": {
                "agent1": {
                    "module": "agents.agent1",
                    "class": "Agent1",
                    # No prompts defined
                }
            },
        }

        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=empty_config),
        ):
            # Test directly calling the function
            result = cli_runner.invoke(list_prompts)
            assert result.exit_code == 0
            assert "No prompts defined in the project" in result.output

    def test_prompts_list_invalid_agent(self, cli_runner, mock_project_config):
        """Test the prompts list command with an invalid agent name."""
        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
            patch("sys.exit") as mock_exit,
        ):
            # Mock sys.exit to prevent test termination
            mock_exit.side_effect = SystemExit(1)

            # Test with non-existent agent
            result = cli_runner.invoke(list_prompts, ["--agent", "nonexistent_agent"])
            assert "Agent 'nonexistent_agent' not found in project configuration" in result.output

    def test_prompts_list_string_agent_config(self, cli_runner):
        """Test the prompts list command with an agent that has a string config."""
        config_with_string = {
            "name": "test_project",
            "version": "0.1.0",
            "agents": {"string_agent": "agents/string_agent"},
        }

        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=config_with_string),
        ):
            result = cli_runner.invoke(list_prompts)
            assert result.exit_code == 0
            assert "No prompts defined in the project" in result.output

    def test_prompts_command_group(self, cli_runner):
        """Test the prompts command group."""
        result = cli_runner.invoke(prompts)
        assert result.exit_code == 0
        assert "Manage prompts in an OpenMAS project" in result.output

    def test_load_project_config_error(self, cli_runner):
        """Test handling of errors when loading project config."""
        # Test with explicit project_dir parameter
        with (
            patch("pathlib.Path.cwd", return_value=Path("/fake/cwd")),
            patch("openmas.config._find_project_root", return_value=None),
            patch("sys.exit", side_effect=SystemExit(1)) as mock_exit,
            patch("click.echo") as mock_echo,
        ):
            from openmas.cli.prompts import _load_project_config

            with pytest.raises(SystemExit):
                _load_project_config(Path("/explicit/path"))

            # Check if the correct error message was echoed
            mock_echo.assert_any_call(
                "❌ Project configuration file 'openmas_project.yml' not found in specified directory: /explicit/path"
            )

            # Verify mock_exit was called
            mock_exit.assert_called_once_with(1)

    def test_prompts_render_command(self, cli_runner, mock_project_config):
        """Test the prompts render command."""
        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
            patch("openmas.cli.prompts.SimpleTemplateRenderer.format") as mock_format,
        ):
            # Mock the format method to return a formatted prompt
            mock_format.return_value = "Hello, Test User!"

            # Test rendering a prompt with variables
            result = cli_runner.invoke(prompts, ["render", "agent1", "greeting", "--var", "name=Test User"])
            assert result.exit_code == 0
            assert "Hello, Test User!" in result.output
            mock_format.assert_called_once_with({"name": "Test User"})

    def test_prompts_render_file_template(self, cli_runner, mock_project_config):
        """Test rendering a prompt with a file template."""
        # We need to properly mock the file opening
        mocked_open = mock_open(read_data="Goodbye, {{name}}!")

        with (
            patch("openmas.cli.prompts._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
            patch.object(Path, "exists", return_value=True),
            patch("builtins.open", mocked_open),
        ):
            # Test rendering a file-based prompt
            result = cli_runner.invoke(prompts, ["render", "agent1", "farewell", "--var", "name=Test User"])
            assert result.exit_code == 0
            assert "Goodbye, Test User!" in result.output

            # Verify the file was opened
            mocked_open.assert_called_once()

    def test_prompts_render_missing_variables(self, cli_runner, mock_project_config):
        """Test rendering a prompt with missing required variables."""
        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
        ):
            # Test with no variables provided
            result = cli_runner.invoke(prompts, ["render", "agent1", "greeting"])
            assert result.exit_code == 0
            assert "Required variables for prompt 'greeting':" in result.output
            assert "name" in result.output
            assert "Use --var key=value to provide values for variables" in result.output

    def test_prompts_render_invalid_variable_format(self, cli_runner, mock_project_config):
        """Test rendering a prompt with an invalid variable format."""
        with (
            patch("openmas.config._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
            patch("sys.exit", side_effect=SystemExit(1)),
        ):
            # Test with invalid variable format (missing '=')
            result = cli_runner.invoke(
                prompts, ["render", "agent1", "greeting", "--var", "invalid-format"], catch_exceptions=True
            )
            assert "Invalid variable format" in result.output

    def test_prompts_render_invalid_prompt_config(self, cli_runner):
        """Test rendering a prompt with neither template nor template_file defined."""
        config_with_invalid_prompt = {
            "name": "test_project",
            "version": "0.1.0",
            "agents": {
                "invalid_agent": {
                    "module": "agents.invalid",
                    "class": "InvalidAgent",
                    "prompts": [
                        {"name": "invalid_prompt", "input_variables": ["name"]},
                    ],
                },
            },
        }

        with (
            patch("openmas.cli.prompts._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=config_with_invalid_prompt),
        ):
            result = cli_runner.invoke(
                prompts, ["render", "invalid_agent", "invalid_prompt", "--var", "name=Test"], catch_exceptions=True
            )
            assert "Prompt has neither 'template' nor 'template_file' defined" in result.output

    def test_prompts_render_no_prompts_defined(self, cli_runner):
        """Test rendering a prompt for an agent with no prompts defined."""
        no_prompts_config = {
            "name": "test_project",
            "version": "0.1.0",
            "agents": {
                "empty_agent": {
                    "module": "agents.empty",
                    "class": "EmptyAgent",
                    # No prompts defined
                },
            },
        }

        with (
            patch("openmas.cli.prompts._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=no_prompts_config),
        ):
            result = cli_runner.invoke(prompts, ["render", "empty_agent", "any_prompt"], catch_exceptions=True)
            assert "No prompts defined for agent" in result.output

    def test_prompts_render_template_file_not_found(self, cli_runner, mock_project_config):
        """Test rendering a prompt with a template file that doesn't exist."""
        with (
            patch("openmas.cli.prompts._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
            patch.object(Path, "exists", lambda path: "farewell.txt" not in str(path)),
        ):
            result = cli_runner.invoke(
                prompts, ["render", "agent1", "farewell", "--var", "name=Test User"], catch_exceptions=True
            )
            assert "Template file not found" in result.output

    def test_prompts_render_template_file_read_error(self, cli_runner, mock_project_config):
        """Test rendering a prompt with a template file that can't be read."""
        with (
            patch("openmas.cli.prompts._find_project_root", return_value=Path("/fake/path")),
            patch("openmas.cli.prompts._load_project_config", return_value=mock_project_config),
            patch.object(Path, "exists", return_value=True),
            patch("builtins.open", side_effect=IOError("Mock file read error")),
        ):
            result = cli_runner.invoke(
                prompts, ["render", "agent1", "farewell", "--var", "name=Test User"], catch_exceptions=True
            )
            assert "Error reading template file" in result.output


class TestSimpleTemplateRenderer:
    """Tests for the SimpleTemplateRenderer class."""

    def test_simple_template_renderer(self):
        """Test the SimpleTemplateRenderer format method."""
        template = "Hello, {{name}}! Welcome to {{place}}."
        renderer = SimpleTemplateRenderer(template=template, input_variables=["name", "place"])

        # Test successful formatting
        result = renderer.format({"name": "John", "place": "Paris"})
        assert result == "Hello, John! Welcome to Paris."

        # Test missing variable handling
        with pytest.raises(KeyError):
            renderer.format({"name": "John"})

        # Test extra variables are ignored
        result = renderer.format({"name": "John", "place": "Paris", "extra": "value"})
        assert result == "Hello, John! Welcome to Paris."
