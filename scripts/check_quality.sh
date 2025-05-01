#!/bin/bash

# ======================================================================
# check_quality.sh - Convenience script to run all code quality checks
# ======================================================================
# This script simplifies running all the code quality checks with one command.
# It uses tox environments to ensure consistent checks across local and CI environments.
#
# Usage:
#   ./scripts/check_quality.sh       # Run all checks
#   ./scripts/check_quality.sh lint  # Run just linting checks
#   ./scripts/check_quality.sh test  # Run just tests (unit and mock integration)
#   ./scripts/check_quality.sh docs  # Run just documentation checks
#
# Requirements:
#   - Poetry (installed and configured)
#   - Tox (installed via poetry)
# ======================================================================

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Keep track of failures
failures=0

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}Running OpenMAS code quality checks...${NC}"
echo -e "${BLUE}======================================================================${NC}"

# Allow running specific check categories
check_type="${1:-all}"

if [ "$check_type" = "all" ] || [ "$check_type" = "lint" ]; then
    echo -e "${BLUE}=== Running linting checks (black, isort, flake8, mypy) ===${NC}"
    if ! poetry run tox -e lint; then
        echo -e "${RED}❌ Linting checks failed${NC}"
        failures=$((failures+1))
    else
        echo -e "${GREEN}✅ Linting checks passed${NC}"
    fi
fi

if [ "$check_type" = "all" ] || [ "$check_type" = "test" ]; then
    echo -e "${BLUE}=== Running unit tests ===${NC}"
    if ! poetry run tox -e unit; then
        echo -e "${RED}❌ Unit tests failed${NC}"
        failures=$((failures+1))
    else
        echo -e "${GREEN}✅ Unit tests passed${NC}"
    fi

    echo -e "${BLUE}=== Running mock integration tests ===${NC}"
    if ! poetry run tox -e integration-mock; then
        echo -e "${RED}❌ Mock integration tests failed${NC}"
        failures=$((failures+1))
    else
        echo -e "${GREEN}✅ Mock integration tests passed${NC}"
    fi
fi

if [ "$check_type" = "all" ] || [ "$check_type" = "docs" ]; then
    echo -e "${BLUE}=== Checking documentation build ===${NC}"
    if ! poetry run tox -e mkdocs-check; then
        echo -e "${RED}❌ Documentation build failed${NC}"
        failures=$((failures+1))
    else
        echo -e "${GREEN}✅ Documentation build passed${NC}"
    fi
fi

echo -e "${BLUE}======================================================================${NC}"
if [ $failures -eq 0 ]; then
    echo -e "${GREEN}All checks passed! 🎉${NC}"
    exit 0
else
    echo -e "${RED}❌ $failures check(s) failed.${NC}"
    echo -e "${YELLOW}Troubleshooting tips:${NC}"
    echo -e "  - Run 'poetry run black .' to auto-format code"
    echo -e "  - Run 'poetry run isort .' to auto-sort imports"
    echo -e "  - Run 'poetry run tox -e lint' to see specific linting errors"
    echo -e "  - Run 'poetry run tox -e mkdocs-check' to check documentation build"
    echo -e "  - Run 'poetry run pre-commit run --all-files' to run all pre-commit hooks"
    exit 1
fi
