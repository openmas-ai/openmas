#!/usr/bin/env python
"""
Script to run mypy on all example directories individually.

This avoids namespace conflicts when multiple example directories have the same module name
(like 'agents'). This is a more scalable solution than listing each example directory in tox.ini.
"""

import os
import subprocess
import sys
from pathlib import Path


def find_example_directories(base_dir: str) -> list[str]:
    """Find all example directories in the base directory."""
    examples_dir = Path(base_dir) / "examples"
    if not examples_dir.exists():
        print(f"Examples directory {examples_dir} not found.")
        return []

    # Find all directories in the examples directory that match our naming pattern
    example_dirs = []
    for item in examples_dir.iterdir():
        if item.is_dir() and item.name.startswith("example_"):
            # For each example directory, find its subdirectories
            for subdir in item.iterdir():
                if subdir.is_dir():
                    example_dirs.append(str(subdir))

    return example_dirs


def run_mypy_on_directory(directory: str, config_file: str) -> bool:
    """Run mypy on a single directory."""
    cmd = ["python", "-m", "mypy", "--config-file", config_file, directory]
    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            # Only print errors if there are real type errors, not just missing imports
            if "error:" in result.stdout and not all(
                "module is installed, but missing library stubs or py.typed marker" in line
                for line in result.stdout.splitlines()
                if "error:" in line
            ):
                print(result.stdout)
                return False
        return True
    except Exception as e:
        print(f"Error running mypy on {directory}: {e}")
        return False


def main():
    """Main function to run mypy on all example directories."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_file = os.path.join(base_dir, "mypy.ini")
    example_dirs = find_example_directories(base_dir)

    if not example_dirs:
        print("No example directories found.")
        return 0

    print(f"Found {len(example_dirs)} example directories.")

    success = True
    for directory in example_dirs:
        if not run_mypy_on_directory(directory, config_file):
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
