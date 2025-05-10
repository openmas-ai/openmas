"""CLI commands for asset management."""

import asyncio
import shutil
import sys
from pathlib import Path  # noqa: F401
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from openmas.assets.exceptions import AssetError
from openmas.assets.manager import AssetManager
from openmas.cli.utils import load_project_config
from openmas.logging import get_logger

logger = get_logger(__name__)
console = Console()

# Create a typer app for the assets commands
assets_app = typer.Typer(help="Manage OpenMAS assets")


@assets_app.command("list")
def list_assets() -> None:
    """List all configured assets and their status."""
    try:
        # Load the project configuration
        project_config = load_project_config()

        # Create an asset manager
        asset_manager = AssetManager(project_config)

        # Create a table for displaying the assets
        table = Table(title="OpenMAS Assets")

        # Add columns to the table
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Type", style="blue")
        table.add_column("Source", style="magenta")
        table.add_column("Checksum", style="yellow")
        table.add_column("Status", style="red")
        table.add_column("Cache Path", style="dim")

        # Add rows for each asset
        for asset in project_config.assets:
            # Check the status of the asset
            status = asset_manager.check_asset_status(asset)

            # Format the status text
            status_text = "Cached" if status["exists"] else "Not cached"
            if status["exists"] and not status["verified"]:
                status_text = "Invalid checksum"

            # Format the source information
            if asset.source.type == "http":
                source_info = f"http: {asset.source.url}"
            elif asset.source.type == "hf":
                source_info = f"hf: {asset.source.repo_id}"
            elif asset.source.type == "local":
                source_info = f"local: {asset.source.path}"
            else:
                source_info = f"{asset.source.type}: unknown"

            # Add a row for this asset
            table.add_row(
                asset.name,
                asset.version or "latest",
                asset.asset_type or "model",
                source_info,
                asset.checksum or "None",
                status_text,
                str(status["path"]) if status["path"] else "Not cached",
            )

        # Print the table
        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error listing assets: {str(e)}[/bold red]")
        sys.exit(1)


@assets_app.command("download")
def download_asset(
    asset_name: str,
    force: bool = typer.Option(False, "--force", "-f", help="Force re-download even if the asset exists in cache."),
) -> None:
    """Download an asset to the cache.

    Args:
        asset_name: The name of the asset to download.
        force: If True, force re-download even if the asset already exists in cache.
    """
    try:
        # Load the project configuration
        project_config = load_project_config()

        # Create an asset manager
        asset_manager = AssetManager(project_config)

        # Find the asset configuration
        asset_found = False
        for asset in project_config.assets:
            if asset.name == asset_name:
                asset_found = True
                break

        if not asset_found:
            console.print(f"[bold red]Asset '{asset_name}' not found in project configuration[/bold red]")
            sys.exit(1)

        # Show progress during download
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[bold green]Downloading asset {asset_name}{'(forced)' if force else ''}...[/bold green]"),
            transient=True,
        ) as progress:
            progress.add_task(f"Downloading {asset_name}", total=None)

            # Download the asset (run synchronously)
            try:
                asset_path = asyncio.run(asset_manager.get_asset_path(asset_name, force_download=force))
                console.print(f"[bold green]Successfully downloaded asset '{asset_name}' to {asset_path}[/bold green]")
            except KeyError as e:
                console.print(f"[bold red]Asset '{asset_name}' not found: {str(e)}[/bold red]")
                sys.exit(1)
            except AssetError as e:
                console.print(f"[bold red]Error downloading asset '{asset_name}': {str(e)}[/bold red]")
                sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error downloading asset: {str(e)}[/bold red]")
        sys.exit(1)


@assets_app.command("verify")
def verify_assets(
    asset_name: Optional[str] = typer.Argument(None, help="Asset name to verify, or all if omitted")
) -> None:
    """Verify the integrity of cached assets.

    Args:
        asset_name: The name of the asset to verify. If not provided, verify all assets.
    """
    try:
        # Load the project configuration
        project_config = load_project_config()

        # Create an asset manager
        asset_manager = AssetManager(project_config)

        if asset_name:
            # Verify a specific asset
            asset_found = False
            for asset in project_config.assets:
                if asset.name == asset_name:
                    asset_found = True

                    # Check the status of the asset
                    status = asset_manager.check_asset_status(asset)

                    if not status["exists"]:
                        console.print(f"[bold yellow]Asset '{asset_name}' is not cached[/bold yellow]")
                        sys.exit(0)

                    if status["verified"]:
                        console.print(f"[bold green]Asset '{asset_name}' is cached and verified[/bold green]")
                        sys.exit(0)
                    else:
                        console.print(f"[bold red]Asset '{asset_name}' has failed verification[/bold red]")
                        sys.exit(1)

            if not asset_found:
                console.print(f"[bold red]Asset '{asset_name}' not found in project configuration[/bold red]")
                sys.exit(1)
        else:
            # Verify all assets
            all_verified = True
            assets_checked = 0

            for asset in project_config.assets:
                # Check the status of the asset
                status = asset_manager.check_asset_status(asset)

                if not status["exists"]:
                    console.print(f"[yellow]{asset.name}: Not cached[/yellow]")
                    continue

                assets_checked += 1

                if status["verified"]:
                    console.print(f"[green]{asset.name}: Verified[/green]")
                else:
                    console.print(f"[red]{asset.name}: Failed verification[/red]")
                    all_verified = False

            if assets_checked == 0:
                console.print("[yellow]No assets are currently cached[/yellow]")
                sys.exit(0)

            if not all_verified:
                console.print("[bold red]Some assets failed verification[/bold red]")
                sys.exit(1)
            else:
                console.print("[bold green]All cached assets are verified[/bold green]")
                sys.exit(0)

    except Exception as e:
        console.print(f"[bold red]Error verifying assets: {str(e)}[/bold red]")
        sys.exit(1)


@assets_app.command("clear-cache")
def clear_cache(
    asset_name: Optional[str] = typer.Option(None, "--asset", "-a", help="Asset name to clear"),
    all_assets: bool = typer.Option(False, "--all", help="Clear the entire asset cache"),
) -> None:
    """Clear asset caches.

    Args:
        asset_name: The name of a specific asset to clear from the cache.
        all_assets: If True, clear the entire asset cache.
    """
    try:
        # Load the project configuration
        project_config = load_project_config()

        # Create an asset manager
        asset_manager = AssetManager(project_config)

        if asset_name and all_assets:
            console.print("[bold red]Cannot specify both --asset and --all[/bold red]")
            sys.exit(1)

        if not asset_name and not all_assets:
            console.print("[bold yellow]Must specify either --asset or --all[/bold yellow]")
            sys.exit(1)

        if all_assets:
            # Clear the entire cache
            confirm = typer.confirm("Are you sure you want to clear the entire asset cache?")
            if not confirm:
                console.print("[yellow]Operation cancelled[/yellow]")
                sys.exit(0)

            # Clear only the contents, not the directory itself
            # Also preserve the .locks directory
            locks_dir = asset_manager.locks_dir
            cache_dir = asset_manager.cache_dir

            # Remove everything except the .locks directory
            for item in cache_dir.iterdir():
                if item != locks_dir:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            console.print("[bold green]Successfully cleared entire assets cache[/bold green]")
        else:
            # Clear a specific asset
            asset_found = False
            for asset in project_config.assets:
                if asset.name == asset_name:
                    asset_found = True

                    # Get the cache path for this asset
                    cache_path = asset_manager._get_cache_path_for_asset(asset)

                    if not cache_path.exists():
                        console.print(f"[yellow]Asset '{asset_name}' is not cached[/yellow]")
                        sys.exit(0)

                    confirm = typer.confirm(f"Are you sure you want to clear the cache for asset '{asset_name}'?")
                    if not confirm:
                        console.print("[yellow]Operation cancelled[/yellow]")
                        sys.exit(0)

                    # Delete the cache directory for this asset
                    if cache_path.is_dir():
                        shutil.rmtree(cache_path)
                    else:
                        cache_path.unlink()

                    console.print(f"[bold green]Successfully cleared cache for asset '{asset_name}'[/bold green]")
                    break

            if not asset_found:
                console.print(f"[bold red]Asset '{asset_name}' not found in project configuration[/bold red]")
                sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error clearing cache: {str(e)}[/bold red]")
        sys.exit(1)
