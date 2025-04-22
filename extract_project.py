#!/usr/bin/env python3
"""
Script to extract critical files from the SimpleMAS project for code review.

This script creates a temporary directory with a copy of the important project files,
excluding binary files, cache directories, and other non-essential files.
"""

import argparse
import fnmatch
import glob
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


def is_excluded(path: str, exclude_patterns: list) -> bool:
    """Check if a path should be excluded based on patterns."""
    path_parts = path.split(os.sep)

    for pattern in exclude_patterns:
        # Check if the pattern matches any part of the path
        if any(fnmatch.fnmatch(part, pattern) for part in path_parts):
            return True
        # Also check the full path
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def should_include(path: str, include_patterns: list) -> bool:
    """Check if a path should be explicitly included based on patterns."""
    # If no include patterns are specified, include all files that aren't excluded
    if not include_patterns:
        return True

    for pattern in include_patterns:
        if fnmatch.fnmatch(path, pattern):
            return True

        # Try to match with glob pattern
        if glob.escape(pattern) != pattern:  # Check if it's a glob pattern
            try:
                matched_files = glob.glob(pattern, recursive=True)
                if path in matched_files or os.path.abspath(path) in matched_files:
                    return True
            except Exception:
                pass  # If glob fails, just continue with other patterns

    return False


def copy_project_files(
    source_dir: str, target_dir: str, include_patterns: list, exclude_patterns: list
) -> Tuple[List[str], List[str]]:
    """Copy project files, preserving directory structure."""
    source_path = Path(source_dir).resolve()
    target_path = Path(target_dir).resolve()

    # Track copied files for summary
    copied_files = []
    skipped_files = []

    for root, dirs, files in os.walk(source_path):
        # Skip excluded directories
        for i, d in reversed(list(enumerate(dirs))):
            dir_path = os.path.join(root, d)
            if is_excluded(dir_path, exclude_patterns):
                del dirs[i]

        # Process files
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, source_path)

            # Skip excluded files
            if is_excluded(file_path, exclude_patterns) or is_excluded(rel_path, exclude_patterns):
                skipped_files.append(rel_path)
                continue

            # If we're filtering for critical files, check if this file should be included
            if include_patterns and not (
                should_include(file_path, include_patterns) or should_include(rel_path, include_patterns)
            ):
                skipped_files.append(rel_path)
                continue

            # Calculate the target file path
            target_file = target_path / rel_path

            # Create directory structure
            os.makedirs(os.path.dirname(target_file), exist_ok=True)

            # Copy the file
            shutil.copy2(file_path, target_file)
            copied_files.append(rel_path)
            print(f"Copied: {rel_path}")

    return copied_files, skipped_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract critical project files for code review.")
    parser.add_argument("--source", default=".", help="Source directory (default: current directory)")
    parser.add_argument("--target", help="Target directory (default: creates a temporary directory)")
    parser.add_argument("--compress", action="store_true", help="Create a zip archive")
    parser.add_argument(
        "--include-only-critical", action="store_true", help="Only include files matching critical patterns"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed information about files processed")
    args = parser.parse_args()

    # Define critical file patterns to explicitly include
    critical_patterns = [
        # Source code (with explicit paths for this project)
        "src/**/*.py",
        "tests/**/*.py",
        "tests/*.py",  # For top-level test files
        "examples/**/*.py",
        # Documentation
        "docs/**/*.md",
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "LICENSE",
        "GettingStarted.md",
        "Architecture.md",
        # Configuration
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        ".flake8",
        "mypy.ini",
        "pytest.ini",
        ".pre-commit-config.yaml",
        # Requirements
        "requirements.txt",
        "requirements-dev.txt",
        "poetry.lock",
    ]

    # Define patterns to exclude
    exclude_patterns = [
        # Directories to exclude
        "__pycache__",
        ".pytest_cache",
        ".git",
        ".venv",
        "venv",
        ".env",
        "env",
        ".tox",
        "build",
        "dist",
        ".idea",
        ".vscode",
        ".mypy_cache",
        ".coverage",
        ".eggs",
        "htmlcov",
        # File extensions to exclude
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.dylib",
        "*.dll",
        "*.exe",
        "*.bin",
        "*.dat",
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        "*.coverage",
        "*.log",
        "*.swp",
        "*.swo",
        # Specific files to exclude
        ".DS_Store",
        ".gitignore",
        ".gitattributes",
    ]

    # Create target directory if not specified
    if args.target:
        target_dir = args.target
    else:
        temp_dir = tempfile.mkdtemp(prefix="simple-mas-review-")
        target_dir = temp_dir

    print(f"Extracting critical files from {args.source} to {target_dir}")

    # Use include patterns only if --include-only-critical is specified
    include_patterns = critical_patterns if args.include_only_critical else []

    # Copy the files
    copied_files, skipped_files = copy_project_files(args.source, target_dir, include_patterns, exclude_patterns)

    # Create archive if requested
    if args.compress:
        archive_name = "simple-mas-review"
        archive_path = shutil.make_archive(archive_name, "zip", target_dir)
        print(f"\nCreated archive: {os.path.abspath(archive_path)}")

    print(f"\nProject files extracted to: {os.path.abspath(target_dir)}")
    print(f"Total files copied: {len(copied_files)}")

    # Print file types summary
    file_types: Dict[str, int] = {}
    for file in copied_files:
        ext = os.path.splitext(file)[1].lower()
        file_types[ext] = file_types.get(ext, 0) + 1

    print("\nFile types summary:")
    for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
        ext_name = ext if ext else "(no extension)"
        print(f"  {ext_name}: {count} files")

    if args.verbose:
        print("\nSkipped files: ", len(skipped_files))
        if include_patterns:
            print("\nCritical patterns used for filtering:")
            for pattern in include_patterns:
                print(f"  {pattern}")


if __name__ == "__main__":
    main()
