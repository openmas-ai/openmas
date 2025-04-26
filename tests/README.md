# OpenMAS Testing Strategy

This document outlines the testing strategy for the `openmas` library, providing guidance on test types, locations, and execution.

## Goals

The OpenMAS testing framework addresses several key goals:

- Ensure correctness of individual components
- Prevent regressions when implementing new features
- Validate framework behavior in isolation and integration
- Properly test optional features and communicators
- Provide end-to-end validation via example applications

## Tooling

OpenMAS uses standard Python testing tools:

- `pytest`: Primary test runner
- `pytest-asyncio`: Testing async code
- `pytest-mock`: Mocking dependencies
- `tox`: Test automation and environment management

## Test Levels & Locations

### Unit Tests (`tests/unit/`)

Unit tests validate individual components in isolation, with all external dependencies mocked. These tests ensure core functionality works as expected without depending on external systems.

- **Location:** `tests/unit/`
- **Purpose:** Test individual classes and functions with complete isolation
- **Execution:** All base `tox` environments run unit tests
- **Dependencies:** External dependencies (Communicators, I/O, etc.) are always mocked

### Integration Tests (`tests/integration/`)

Integration tests validate interactions between components. They are subdivided based on dependency requirements:

#### Core Integration Tests (`tests/integration/core/`)

- **Location:** `tests/integration/core/`
- **Purpose:** Test core feature interactions without optional extras
- **Execution:** All base `tox` environments run core integration tests
- **Dependencies:** May use mocks for external systems, but test interactions between core components

#### Optional Dependency Integration Tests

These tests validate integration with specific communicators using the actual libraries:

- **MCP Tests:** `tests/integration/mcp/`
- **gRPC Tests:** `tests/integration/grpc/`
- **MQTT Tests:** `tests/integration/mqtt/`

These tests:
- Run only in dedicated `tox` environments with appropriate extras installed
- Use pytest markers (e.g., `@pytest.mark.mcp`) for categorization
- Test against real dependencies, not mocks
- Will be skipped if dependencies are unavailable

### Example Tests (`examples/*/test_example.py`)

Example tests run the actual example applications end-to-end:

- **Location:** `examples/*/test_example.py`
- **Purpose:** Framework dogfooding and end-to-end feature validation
- **Execution:** Dedicated `tox` environments (e.g., `example-hello-agent`)
- **Note:** These tests validate framework functionality in context and are not intended as user test patterns

## Running Tests via `tox`

`tox` is the recommended way to run tests with proper dependency management:

- `tox`: Run all defined environments (lint, unit, integration, examples)
- `tox -e pyXY`: Run core unit and integration tests for Python XY
- `tox -e pyXY-mcp`: Run MCP integration tests for Python XY
- `tox -e pyXY-grpc`: Run gRPC integration tests for Python XY
- `tox -e pyXY-mqtt`: Run MQTT integration tests for Python XY
- `tox -e example-hello-agent`: Run the hello-agent example tests
- `tox -e lint`: Run linting checks only

**Important:** Running `pytest` directly might lead to many skipped tests if optional dependencies aren't manually installed. Using `tox` ensures the right dependencies are available for each test type.

## Handling Optional Dependencies

OpenMAS handles optional dependencies through:

1. **Tox environments with extras:** Dedicated environments install specific extras (e.g., `mcp`, `grpc`, `mqtt`)
2. **Integration test organization:** Tests requiring specific extras run only in matching environments
3. **Pytest markers:** Tests use markers (e.g., `@pytest.mark.mcp`) to identify dependency requirements
4. **Conditional skipping:** Module-level `skipif` in unit tests as a safeguard when a test truly cannot be mocked

## Mocking Strategy

Different test levels use different mocking approaches:

- **Unit tests:** All external dependencies are mocked (`pytest-mock`)
- **Core integration tests:** May use mocks for external systems
- **Optional dependency integration tests:** Use real libraries, not mocks
- **Example tests:** Run actual example code against real dependencies

## Contribution Guide

When contributing tests to OpenMAS:

1. Add unit tests to `tests/unit/` matching the module structure in `src/`
2. Add core integration tests to `tests/integration/core/` if they don't require optional extras
3. Add optional dependency tests to the appropriate directory (e.g., `tests/integration/mcp/`)
4. Ensure tests use appropriate markers for skipping or categorization
5. Verify tests run in the appropriate `tox` environment(s)
6. Remember: unit tests must always use mocks for external dependencies and never rely on their actual presence
