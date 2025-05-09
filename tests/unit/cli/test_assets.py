"""Tests for the assets CLI commands."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from openmas.assets.config import AssetConfig, AssetSourceConfig
from openmas.assets.exceptions import AssetError
from openmas.assets.manager import AssetManager
from openmas.cli.assets import assets_app
from openmas.config import ProjectConfig


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def asset1():
    """Create a test asset1."""
    source = MagicMock(spec=AssetSourceConfig)
    source.type = "http"
    source.url = "https://example.com/asset1"

    asset = MagicMock(spec=AssetConfig)
    asset.name = "asset1"
    asset.version = "1.0.0"
    asset.asset_type = "model"
    asset.source = source
    asset.checksum = "sha256:1234567890abcdef"
    asset.unpack = False
    asset.description = "Asset 1"

    return asset


@pytest.fixture
def asset2():
    """Create a test asset2."""
    source = MagicMock(spec=AssetSourceConfig)
    source.type = "hf"
    source.repo_id = "user/repo"

    asset = MagicMock(spec=AssetConfig)
    asset.name = "asset2"
    asset.version = "2.0.0"
    asset.asset_type = "dataset"
    asset.source = source
    asset.checksum = None
    asset.unpack = True
    asset.unpack_format = "zip"
    asset.description = "Asset 2"

    return asset


@pytest.fixture
def mock_project_config(asset1, asset2):
    """Create a mock project configuration with assets."""
    config = MagicMock(spec=ProjectConfig)
    config.assets = [asset1, asset2]
    return config


@pytest.fixture
def mock_asset_manager():
    """Create a mock asset manager."""
    manager = MagicMock(spec=AssetManager)
    manager.get_asset_path = AsyncMock()
    manager.verify_asset = MagicMock()
    # Dictionary to store asset status information
    manager.check_asset_status = MagicMock()
    return manager


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
def test_list_command(
    mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager, asset1, asset2
):
    """Test that the list command produces the expected output."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager

    # Configure mock status responses
    def check_status(asset):
        if asset.name == "asset1":
            return {
                "exists": True,
                "verified": True,
                "path": Path(f"/cache/path/{asset.name}"),
            }
        else:
            return {
                "exists": False,
                "verified": False,
                "path": None,
            }

    mock_asset_manager.check_asset_status.side_effect = check_status

    # Run the command
    result = cli_runner.invoke(assets_app, ["list"])

    # Print debug information
    print("\nEXIT CODE:", result.exit_code)
    print("STDOUT:", result.stdout)
    if hasattr(result, "exception") and result.exception:
        print("EXCEPTION:", repr(result.exception))

    # Verify the result
    assert result.exit_code == 0
    assert "asset1" in result.stdout
    assert "asset2" in result.stdout
    assert "model" in result.stdout
    assert "dataset" in result.stdout
    assert "http" in result.stdout
    assert "hf" in result.stdout
    assert "Cached" in result.stdout
    assert "Not cached" in result.stdout


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
def test_download_command_success(
    mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager, asset1
):
    """Test the download command when successful."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager
    mock_asset_manager.get_asset_path.return_value = Path("/cache/path/asset1")

    # Print information about mock assets in project config
    print("\nASSETS IN PROJECT CONFIG:")
    for asset in mock_project_config.assets:
        print(f"  - {asset.name} (type: {type(asset)})")

    # Run the command
    result = cli_runner.invoke(assets_app, ["download", "asset1"])

    # Print debug information
    print("\nEXIT CODE:", result.exit_code)
    print("STDOUT:", result.stdout)
    if hasattr(result, "exception") and result.exception:
        print("EXCEPTION:", repr(result.exception))

    # Verify the result
    assert result.exit_code == 0
    assert "Successfully downloaded asset" in result.stdout
    mock_asset_manager.get_asset_path.assert_called_once_with("asset1")


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
def test_download_command_not_found(
    mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager
):
    """Test the download command when asset is not found."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager
    mock_asset_manager.get_asset_path.side_effect = KeyError("Asset 'nonexistent' not found")

    # Run the command
    result = cli_runner.invoke(assets_app, ["download", "nonexistent"])

    # Verify the result
    assert result.exit_code != 0
    assert "not found" in result.stdout


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
def test_download_command_error(
    mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager
):
    """Test the download command when an error occurs."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager
    mock_asset_manager.get_asset_path.side_effect = AssetError("Download failed")

    # Run the command
    result = cli_runner.invoke(assets_app, ["download", "asset1"])

    # Verify the result
    assert result.exit_code != 0
    assert "Download failed" in result.stdout


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
def test_verify_single_asset(
    mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager, asset1
):
    """Test verifying a single asset."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager

    mock_asset_manager.check_asset_status.return_value = {
        "exists": True,
        "verified": True,
        "path": Path("/cache/path/asset1"),
    }

    # Run the command
    result = cli_runner.invoke(assets_app, ["verify", "asset1"])

    # Print debug information
    print("\nEXIT CODE:", result.exit_code)
    print("STDOUT:", repr(result.stdout))

    # Verify the result
    assert result.exit_code == 0
    assert "cached and verified" in result.stdout.lower()
    assert "asset1" in result.stdout


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
def test_verify_single_asset_fails(
    mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager, asset1
):
    """Test verifying a single asset that fails verification."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager

    mock_asset_manager.check_asset_status.return_value = {
        "exists": True,
        "verified": False,
        "path": Path("/cache/path/asset1"),
    }

    # Run the command
    result = cli_runner.invoke(assets_app, ["verify", "asset1"])

    # Print debug information
    print("\nEXIT CODE:", result.exit_code)
    print("STDOUT:", repr(result.stdout))

    # Verify the result
    assert result.exit_code != 0
    assert "failed verification" in result.stdout.lower()


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
def test_verify_all_assets(
    mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager, asset1, asset2
):
    """Test verifying all assets."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager

    # Configure check_asset_status for different assets
    def check_status(asset):
        if asset.name == "asset1":
            return {"exists": True, "verified": True, "path": Path("/cache/path/asset1")}
        else:
            return {"exists": True, "verified": False, "path": Path("/cache/path/asset2")}

    mock_asset_manager.check_asset_status.side_effect = check_status

    # Run the command
    result = cli_runner.invoke(assets_app, ["verify"])

    # Print debug information
    print("\nEXIT CODE:", result.exit_code)
    print("STDOUT:", repr(result.stdout))

    # Verify the result
    assert result.exit_code != 0  # Should fail because one asset failed verification
    assert "asset1" in result.stdout
    assert "asset2" in result.stdout


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
@patch("openmas.cli.assets.typer.confirm")
@patch("openmas.cli.assets.shutil.rmtree")
@patch("openmas.cli.assets.Path.unlink")
def test_clear_cache_specific_asset(
    mock_unlink,
    mock_rmtree,
    mock_confirm,
    mock_asset_manager_cls,
    mock_load_config,
    cli_runner,
    mock_project_config,
    mock_asset_manager,
    asset1,
):
    """Test clearing cache for a specific asset."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager
    mock_confirm.return_value = True

    # Configure _get_cache_path_for_asset to return a Path with a patched exists method
    cache_path = Path("/cache/path/asset1")
    mock_asset_manager._get_cache_path_for_asset.return_value = cache_path

    # Patch Path.exists and Path.is_dir to simulate directory existence
    with patch.object(Path, "exists", return_value=True), patch.object(Path, "is_dir", return_value=True):
        # Run the command
        result = cli_runner.invoke(assets_app, ["clear-cache", "--asset", "asset1"])

        # Print debug information
        print("\nEXIT CODE:", result.exit_code)
        print("STDOUT:", repr(result.stdout))

        # Verify the result
        assert result.exit_code == 0
        assert "successfully cleared" in result.stdout.lower() or "cleared cache" in result.stdout.lower()

        # Verify rmtree was called with the correct path
        mock_rmtree.assert_called_once_with(cache_path)


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
@patch("openmas.cli.assets.typer.confirm")
@patch("openmas.cli.assets.shutil.rmtree")
@patch("openmas.cli.assets.Path.unlink")
def test_clear_cache_all_assets(
    mock_unlink,
    mock_rmtree,
    mock_confirm,
    mock_asset_manager_cls,
    mock_load_config,
    cli_runner,
    mock_project_config,
    mock_asset_manager,
):
    """Test clearing cache for all assets."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager
    mock_confirm.return_value = True

    # Set up the cache directory on the mock asset manager
    cache_dir = Path("/cache")
    mock_asset_manager.cache_dir = cache_dir
    mock_asset_manager.locks_dir = cache_dir / ".locks"

    # Create mock paths for the cache directory contents
    mock_dir1 = MagicMock(spec=Path)
    mock_dir1.is_dir.return_value = True
    mock_dir1.__str__.return_value = "/cache/dir1"

    mock_file1 = MagicMock(spec=Path)
    mock_file1.is_dir.return_value = False
    mock_file1.__str__.return_value = "/cache/file1"

    # Create a mock locks directory with a proper __eq__ method
    mock_locks_dir = MagicMock(spec=Path)
    mock_locks_dir.__str__.return_value = "/cache/.locks"

    # Make the comparison work when checking if item != locks_dir
    def mock_eq(self, other):
        if isinstance(other, Path):
            return str(self) == str(other)
        return False

    mock_locks_dir.__eq__ = mock_eq

    # Run the command with mocked Path.iterdir to simulate cache directory contents
    with patch("openmas.cli.assets.Path.iterdir") as mock_iterdir:
        # Return our mocked files/dirs when iterdir is called
        mock_iterdir.return_value = [mock_dir1, mock_file1, mock_locks_dir]

        # Run the command
        result = cli_runner.invoke(assets_app, ["clear-cache", "--all"])

        # Print debug information
        print("\nEXIT CODE:", result.exit_code)
        print("STDOUT:", repr(result.stdout))
        print("\nrmtree calls:", mock_rmtree.call_args_list)
        print("unlink calls:", mock_unlink.call_args_list)

        # Verify the result
        assert result.exit_code == 0
        assert "successfully cleared" in result.stdout.lower() or "cleared entire" in result.stdout.lower()

        # Verify at least one delete operation was performed
        assert mock_rmtree.called, "No directories were removed"


@patch("openmas.cli.assets.load_project_config")
@patch("openmas.cli.assets.AssetManager")
@patch("openmas.cli.assets.typer.confirm")
def test_clear_cache_user_cancels(
    mock_confirm, mock_asset_manager_cls, mock_load_config, cli_runner, mock_project_config, mock_asset_manager
):
    """Test user canceling cache clearing."""
    # Setup mocks
    mock_load_config.return_value = mock_project_config
    mock_asset_manager_cls.return_value = mock_asset_manager
    mock_confirm.return_value = False

    # Run the command
    result = cli_runner.invoke(assets_app, ["clear-cache", "--all"])

    # Print debug information
    print("\nEXIT CODE:", result.exit_code)
    print("STDOUT:", repr(result.stdout))

    # Verify the result
    assert result.exit_code == 0
    assert "cancelled" in result.stdout.lower() or "operation cancelled" in result.stdout.lower()
