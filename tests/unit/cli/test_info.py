"""Tests for the CLI info command."""

from click.testing import CliRunner

from openmas import __version__
from openmas.cli.main import cli


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_command_exists(self):
        """Test that the info command exists and is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "info" in result.output

    def test_info_command_output(self):
        """Test that the info command outputs the correct information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert f"OpenMAS version: {__version__}" in result.output
        assert "Python version:" in result.output
        assert "Platform:" in result.output
        assert "Optional modules:" in result.output

    def test_info_command_json_output(self):
        """Test that the info command outputs JSON when requested."""
        runner = CliRunner()
        result = runner.invoke(cli, ["info", "--json"])
        assert result.exit_code == 0
        # JSON output should contain version but not the human-readable strings
        assert __version__ in result.output
        assert "OpenMAS version:" not in result.output

    def test_version_flag(self):
        """Test that the --version flag shows the correct version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
