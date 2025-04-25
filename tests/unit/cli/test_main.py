"""Tests for the CLI main module."""
import importlib


def test_cli_main_module():
    """Test that the CLI main module exists."""
    spec = importlib.util.find_spec("openmas.cli.__main__")
    assert spec is not None, "CLI __main__ module not found"
