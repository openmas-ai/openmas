#!/bin/bash
set -e

# Run all code quality checks

echo "=== Running black ==="
poetry run black --check .

echo "=== Running isort ==="
poetry run isort --check .

echo "=== Running flake8 ==="
poetry run flake8 src tests

echo "=== Running mypy ==="
poetry run mypy src

echo "=== Running pytest ==="
poetry run pytest

echo "All checks passed! 🎉"
