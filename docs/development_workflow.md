# Development Workflow

This document provides an overview of the OpenMAS development workflow, tools, and commands for contributors.

## Development Environment

OpenMAS uses [Poetry](https://python-poetry.org/) for dependency management and [tox](https://tox.readthedocs.io/) for testing across environments.

### Setup

1. Install Poetry (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/dylangames/openmas.git
   cd openmas
   ```

3. Install dependencies:
   ```bash
   poetry install
   ```

4. Install pre-commit hooks:
   ```bash
   poetry run pre-commit install
   ```

## Dependency Management

OpenMAS uses a DRY (Don't Repeat Yourself) approach to dependency management by leveraging Poetry for all dependency definitions in `pyproject.toml`, while tox environments use Poetry to install dependencies as needed.

### How it works

1. All dependencies are defined in `pyproject.toml`:
   - Core dependencies in `[tool.poetry.dependencies]`
   - Dev dependencies in `[tool.poetry.group.dev.dependencies]`
   - Optional dependencies in `[tool.poetry.extras]`

2. The tox environments use Poetry to install dependencies with the correct extras:
   ```ini
   [testenv]
   commands_pre =
       poetry install --with dev {env:TOX_EXTRAS:}
   ```

3. Specific environments that need additional extras (like MCP integration) set environment variables:
   ```ini
   [testenv:integration-mock]
   setenv =
       TOX_EXTRAS = --extras mcp
   ```

This approach ensures that the tox environments always use the same versions of dependencies as defined in `pyproject.toml`, eliminating duplication and potential version conflicts.

## Common Commands

### Linting and Formatting

```bash
# Run all linting checks
poetry run tox -e lint

# Format code directly
poetry run black .
poetry run isort .

# Run flake8 linting
poetry run flake8 src tests examples

# Run type checking with mypy
poetry run mypy --config-file=mypy.ini src tests examples
```

### Unit Tests

```bash
# Run all unit tests
poetry run tox -e unit

# Run specific unit tests
poetry run tox -e unit -- tests/unit/agent/test_specific.py

# Run with pytest directly (faster during development)
poetry run pytest tests/unit/
```

### Integration Tests

```bash
# Run integration tests with mocks (no real dependencies needed)
poetry run tox -e integration-mock

# Run integration tests with MCP (requires MCP setup)
poetry run tox -e integration-real-mcp

# Run integration tests with gRPC
poetry run tox -e integration-real-grpc

# Run integration tests with MQTT
poetry run tox -e integration-real-mqtt
```

### Coverage Report

```bash
# Run tests with coverage report
poetry run tox -e coverage
```

### Documentation

```bash
# Build documentation
poetry run tox -e docs

# Serve documentation locally (after building)
poetry run mkdocs serve
```

### Examples

```bash
# Run the hello agent example
poetry run tox -e example-00a-hello-single
```

## Available Tox Environments

OpenMAS defines the following tox environments:

| Environment | Description |
|-------------|-------------|
| `lint` | Run linting, formatting checks, and type checking |
| `unit` | Run all unit tests (fast, no external deps) |
| `integration-mock` | Run integration tests using mocks (no real services) |
| `integration-real-mcp` | Run real integration tests requiring MCP services |
| `integration-real-grpc` | Run real integration tests requiring gRPC services |
| `integration-real-mqtt` | Run real integration tests requiring MQTT broker |
| `coverage` | Run tests with coverage report |
| `docs` | Build documentation |
| `example-00a-hello-single` | Run the single hello world agent example |

## Continuous Integration

The CI/CD pipeline automatically runs the following checks on pull requests:

1. Linting and static type checking with `tox -e lint`
2. Unit tests with `tox -e unit`
3. Mock integration tests with `tox -e integration-mock`
4. Coverage reporting with `tox -e coverage`

## Troubleshooting

### Dependency Issues

If you encounter dependency-related errors when running tox, try the following steps:

1. Update Poetry and tox to the latest versions:
   ```bash
   pip install --upgrade poetry tox
   ```

2. Update your Poetry lock file:
   ```bash
   poetry update
   ```

3. Clean the tox environments and try again:
   ```bash
   rm -rf .tox
   poetry run tox -e lint
   ```

### Version Pinning

Since the tox.ini environment dependencies now rely on Poetry's dependency resolution, ensure that version constraints in `pyproject.toml` are appropriately specified to avoid CI/local inconsistencies:

- For development tools (like black, flake8, mypy), use exact pins (`black = "==25.1.0"`) to ensure consistent behavior
- For libraries, use appropriate version constraints (`">=x.y.z,<a.b.c"`) as needed
