#!/bin/bash

# Run all code quality checks
echo "======================================================================"
echo "Running all code quality checks..."
echo "======================================================================"

# Keep track of failures
failures=0

echo "=== Running black ==="
if ! poetry run black --check .; then
    echo "❌ black check failed"
    failures=$((failures+1))
else
    echo "✅ black check passed"
fi

echo "=== Running isort ==="
if ! poetry run isort --check .; then
    echo "❌ isort check failed"
    failures=$((failures+1))
else
    echo "✅ isort check passed"
fi

echo "=== Running flake8 ==="
if ! poetry run flake8 src tests; then
    echo "❌ flake8 check failed"
    failures=$((failures+1))
else
    echo "✅ flake8 check passed"
fi

echo "=== Running mypy ==="
if ! poetry run mypy src; then
    echo "❌ mypy check failed (see above for details)"
    failures=$((failures+1))
else
    echo "✅ mypy check passed"
fi

echo "=== Running pytest ==="
if ! poetry run pytest; then
    echo "❌ pytest check failed"
    failures=$((failures+1))
else
    echo "✅ pytest check passed"
fi

echo "======================================================================"
if [ $failures -eq 0 ]; then
    echo "All checks passed! 🎉"
    exit 0
else
    echo "❌ $failures check(s) failed."
    echo "Run 'poetry run pre-commit run --all-files' to fix some issues automatically."
    exit 1
fi
