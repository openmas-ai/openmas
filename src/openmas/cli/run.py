"""CLI run module for OpenMAS."""

import os
import sys
from pathlib import Path


def add_package_paths_to_sys_path(packages_dir: str | Path) -> None:
    """Add package paths to sys.path for dependency resolution.

    Scans the packages directory and adds appropriate paths to sys.path so
    that packages can be imported. For packages with a src directory, it adds
    the src directory. For packages without a src directory, it adds the
    package root directory.

    Args:
        packages_dir: Path to the packages directory
    """
    packages_dir = Path(packages_dir)
    if not os.path.isdir(packages_dir):
        return

    # Skip special directories like .git, __pycache__, etc.
    skip_dirs = {".git", "__pycache__", "__pypackages__", ".tox", ".pytest_cache"}

    # Get all directories in the packages directory
    for package_name in os.listdir(packages_dir):
        package_path = packages_dir / package_name

        # Skip non-directories and special directories
        if not os.path.isdir(package_path) or package_name in skip_dirs or package_name.startswith("."):
            continue

        # Check if this package has a src directory
        src_path = package_path / "src"
        if os.path.isdir(src_path):
            # Add the src directory if it exists
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))
        else:
            # Otherwise add the package root
            if str(package_path) not in sys.path:
                sys.path.insert(0, str(package_path))
