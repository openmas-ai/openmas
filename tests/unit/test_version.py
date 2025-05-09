"""Tests for version detection in the `openmas` package."""

import importlib.metadata
import pathlib
import sys
from unittest import mock

import tomli  # type: ignore

# Define the expected version from pyproject.toml
with open(pathlib.Path(__file__).parents[2] / "pyproject.toml", "rb") as f:
    EXPECTED_VERSION = tomli.load(f)["tool"]["poetry"]["version"]


def test_version_from_metadata():
    """Test that the version is correctly read from package metadata when installed."""
    with mock.patch("importlib.metadata.version", return_value="0.2.0") as mock_version:
        # Re-import to trigger version detection
        import openmas

        importlib.reload(sys.modules.get("openmas"))

        assert openmas.__version__ == "0.2.0"
        mock_version.assert_called_once_with("openmas")


def test_version_from_pyproject():
    """Test that the version is correctly read from pyproject.toml in development mode."""

    # Mock the importlib.metadata.version to raise PackageNotFoundError
    with mock.patch("importlib.metadata.version") as mock_version:
        mock_version.side_effect = importlib.metadata.PackageNotFoundError("openmas")

        # Re-import to trigger version detection
        import openmas

        importlib.reload(sys.modules.get("openmas"))

        # Version should match what's in pyproject.toml
        assert openmas.__version__ == EXPECTED_VERSION


def test_version_pyproject_not_found():
    """Test fallback to development version when pyproject.toml can't be found."""

    # Mock metadata.version to raise PackageNotFoundError
    # and patch the pyproject path search to fail
    with (
        mock.patch("importlib.metadata.version") as mock_version,
        mock.patch("pathlib.Path.exists", return_value=False),
    ):
        mock_version.side_effect = importlib.metadata.PackageNotFoundError("openmas")

        # Re-import to trigger version detection
        import openmas

        importlib.reload(sys.modules.get("openmas"))

        # Should fall back to dev version
        assert openmas.__version__ == "0.0.0-dev"


def test_version_tomli_import_error():
    """Test fallback when tomli can't be imported."""

    # Mock metadata.version to raise PackageNotFoundError
    # and tomli import to fail
    with mock.patch("importlib.metadata.version") as mock_version, mock.patch.dict(sys.modules, {"tomli": None}):
        mock_version.side_effect = importlib.metadata.PackageNotFoundError("openmas")
        sys.modules["tomli"] = None  # Force import error

        # Re-import to trigger version detection
        import openmas

        importlib.reload(sys.modules.get("openmas"))

        # Should fall back to dev version
        assert openmas.__version__ == "0.0.0-dev"

        # Restore tomli module
        if "tomli" in sys.modules:
            del sys.modules["tomli"]


def test_version_parse_error():
    """Test fallback when pyproject.toml can't be parsed properly."""

    # Mock metadata.version to raise PackageNotFoundError
    # and patch tomli.load to raise an error
    with mock.patch("importlib.metadata.version") as mock_version, mock.patch("tomli.load") as mock_load:
        mock_version.side_effect = importlib.metadata.PackageNotFoundError("openmas")
        mock_load.side_effect = KeyError("Could not parse pyproject.toml")

        # Re-import to trigger version detection
        import openmas

        importlib.reload(sys.modules.get("openmas"))

        # Should fall back to dev version
        assert openmas.__version__ == "0.0.0-dev"
