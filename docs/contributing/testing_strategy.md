# OpenMAS Testing Strategy (for Contributors)

This document outlines the testing strategy for the `openmas` framework itself, providing guidance for contributors on test types, locations, and execution.

*For information on how to test applications built **with** OpenMAS, please see the user guide: [Testing Your Agents](../guides/testing-utilities.md).*

## Goals

The OpenMAS internal testing framework addresses several key goals:

- Ensure correctness of individual framework components (agents, communicators, config, etc.).
- Prevent regressions when implementing new features or refactoring.
- Validate framework behavior in isolation and integration scenarios.
- Properly test optional features and communicators (like MCP, gRPC, MQTT).
- Provide end-to-end validation via example applications.

## Testing Philosophy

OpenMAS follows a Test-Driven Development (TDD) approach internally:

1. Write failing tests first.
2. Implement the minimum code required to make the tests pass.
3. Refactor the code while keeping the tests passing.

This ensures that features are well-tested and code quality remains high.

## Tooling

OpenMAS uses standard Python testing tools:

- `pytest`: Primary test runner.
- `pytest-asyncio`: Testing async code.
- `pytest-mock`: Mocking dependencies.
- `tox`: Test automation and environment management via directory targeting.

## Test Levels & Locations

Tests are organized primarily by directory structure within the `tests/` directory, reflecting the type of test and its dependencies.

### Unit Tests (`tests/unit/`)

Unit tests verify isolated components with all external dependencies mocked.

- **Location:** `tests/unit/`
- **Purpose:** Test individual classes and functions (e.g., `BaseAgent` methods, config loading logic) with complete isolation.
- **Dependencies:** External dependencies (Communicators, I/O, network calls, file system access) are **always** mocked using `pytest-mock` or framework utilities like `MockCommunicator`.
- **Execution:** Run via the `tox -e unit` environment.
- **Requirement:** Must never be skipped due to the unavailability of external dependencies. They should be fast and self-contained.

### Integration Tests (`tests/integration/`)

Integration tests verify how framework components work together or interact with external protocols/libraries. They are subdivided based on dependency requirements.

- **Location:** `tests/integration/`
- **Purpose:** Test interactions between components (e.g., `BaseAgent` with `HttpCommunicator`) or with external services/protocols (e.g., connecting to a real MQTT broker).
- **Dependencies:** May use mocks (`MockCommunicator`, `AgentTestHarness`) or actual dependencies (like specific communicator libraries or running services).
- **Execution:** Run via various `tox -e integration-*` environments.
- **Requirement:** Tests relying on *actual external services* (like a running MQTT broker or specific MCP server setup) **must** be skipped (using `pytest.mark.skipif`) if the required service/dependency is unavailable in the test environment. Any test that is executed (not skipped) must pass.

#### Core Integration Tests (`tests/integration/core/`)

- **Location:** `tests/integration/core/`
- **Purpose:** Test core feature interactions without optional extras (e.g., agent lifecycle with `HttpCommunicator`).
- **Execution:** Included in the `tox -e integration-mock` environment.
- **Dependencies:** Primarily test interactions between core components, typically using mocks like `MockCommunicator` or `AgentTestHarness` for simulating communication.

#### Mocked Integration Tests (`tests/integration/<feature>/mock/`)

- **Example Location:** `tests/integration/mcp/mock/`
- **Purpose:** Test integration with optional features (like MCP, gRPC) using mocks instead of real services. Allows testing the integration logic (e.g., how `McpAgent` uses `McpSseCommunicator`) without needing the actual service running.
- **Execution:** Included in the `tox -e integration-mock` environment.
- **Dependencies:** Requires the feature's libraries installed (e.g., `mcp` via `openmas[mcp]`) but mocks the actual service interaction (e.g., using `AgentTestHarness` which injects `MockCommunicator`).

#### Real Service Integration Tests (`tests/integration/<feature>/real/` or `tests/integration/<feature>/`)

- **Example Locations:** `tests/integration/mcp/real/`, `tests/integration/grpc/`, `tests/integration/mqtt/`
- **Purpose:** Test integration with optional features (like MCP, gRPC, MQTT) against *real* services or libraries. These verify the actual communication protocol implementation works correctly.
- **Execution:** Run via dedicated `tox` environments (e.g., `tox -e integration-real-mcp`, `tox -e integration-real-grpc`, `tox -e integration-real-mqtt`).
- **Dependencies:** Require the feature's libraries *and* potentially a running instance of the service (e.g., an MQTT broker, a specific test MCP server). These tests **must** use `pytest.mark.skipif` to check for service availability and skip gracefully if absent.

### Example Tests (`examples/*/`)

Example tests run the actual example applications end-to-end, primarily for framework validation.

- **Location:** `examples/*/` (Test logic often in `test_example.py` within each example).
- **Purpose:** Framework dogfooding and end-to-end feature validation in a realistic context.
- **Execution:** Run via dedicated `tox` environments (e.g., `tox -e example-00a-hello-single`).
- **Note:** These validate that the framework enables the creation of working applications for specific scenarios.

## Running Tests via `tox`

`tox` is the **required** way to run tests for contribution, ensuring isolated environments and correct dependencies based on targeted directories. Use `poetry run tox ...` to ensure tox uses the project's Poetry environment.

### Local Development (Fast Feedback):

These environments are fast and don't require external services.

- `poetry run tox`: Runs the default set: `lint`, `unit`, `integration-mock`.
- `poetry run tox -e lint`: Run linters, formatters (check mode), and type checker.
- `poetry run tox -e unit`: Run only unit tests (very fast).
- `poetry run tox -e integration-mock`: Run core and mocked integration tests.
- `poetry run tox -e coverage`: Run unit and mock integration tests and generate a coverage report.

### Local Development (Specific Real Services):

Run these if you have the corresponding service (e.g., MQTT broker, specific MCP server) running locally and configured.

- `poetry run tox -e integration-real-mcp`: Run MCP integration tests against real services/libs.
- `poetry run tox -e integration-real-grpc`: Run gRPC integration tests against real services/libs.
- `poetry run tox -e integration-real-mqtt`: Run MQTT integration tests against a real MQTT broker.

### CI Pull Request Checks (Fast):

CI should run the fast checks on every pull request:

- `poetry run tox -e lint`
- `poetry run tox -e unit`
- `poetry run tox -e integration-mock`

### Full CI Runs (e.g., on Merge/Release):

Full CI runs should execute all environments, including those requiring real services. The CI environment must be configured to provide these services (e.g., start Docker containers).

- `poetry run tox` (which includes `lint`, `unit`, `integration-mock`)
- `poetry run tox -e integration-real-mcp`
- `poetry run tox -e integration-real-grpc`
- `poetry run tox -e integration-real-mqtt`
- `poetry run tox -e coverage`
- All `example-*` environments.

**Important:** Running `pytest` directly is **discouraged** for final checks as it bypasses the environment setup and dependency management handled by `tox`, potentially leading to incorrect results or missed/incorrectly skipped tests.

## Handling Optional Dependencies

OpenMAS handles optional dependencies primarily through:

1.  **Directory Structure:** Separating tests requiring optional dependencies into specific directories (e.g., `integration/mcp/`, `integration/grpc/`).
2.  **Tox Environments with Extras:** Dedicated `tox` environments (e.g., `integration-mock`, `integration-real-mcp`) install the necessary extras (defined in `pyproject.toml` using `poetry install --extras ...`) and target the relevant test directories.
3.  **Pytest `skipif`:** Tests requiring real services (in `integration/.../real/`) **must** use `pytest.mark.skipif` to check for the availability of the service or necessary libraries/configuration, ensuring they are skipped gracefully if the dependencies aren't met.

## Mocking Strategy

- **Unit tests (`tests/unit/`):** All external dependencies MUST be mocked (`pytest-mock`).
- **Core integration tests (`tests/integration/core/`):** Typically use mocks for external systems (`MockCommunicator`, `AgentTestHarness`).
- **Mocked integration tests (`tests/integration/.../mock/`):** Use the feature's library but mock the actual network/service interaction (e.g., using `MockCommunicator` or specific mocking utilities like `McpTestHarness` configured for mocking).
- **Real service integration tests (`tests/integration/.../real/`):** Use the real libraries and attempt to connect to real services (or test harnesses simulating them).
- **Example tests (`examples/*/`):** Run actual example code, potentially against real services depending on the example.

## Contribution Guide

When contributing tests to OpenMAS:

1.  Add unit tests to `tests/unit/` matching the module structure in `src/`. Ensure all external dependencies are mocked.
2.  Add integration tests for core features (no optional extras) to `tests/integration/core/`. Use mocks where appropriate.
3.  Add integration tests for features requiring optional extras:
    * If the test *mocks* the external service interaction, place it in `tests/integration/<feature>/mock/` (e.g., `tests/integration/mcp/mock/`). Ensure it runs in the `integration-mock` tox environment.
    * If the test requires a *real* service/library interaction, place it in `tests/integration/<feature>/real/` (e.g., `tests/integration/mcp/real/`) or `tests/integration/<feature>/` if no mock/real split exists for that feature. Use `skipif` appropriately for real service tests. Ensure it runs in the correct `integration-real-<feature>` tox environment.
4.  Ensure tests run correctly within their designated `tox` environment(s).
5.  Do **not** rely on `pytest` markers (`@pytest.mark.<feature>`) for controlling test execution; rely on the directory structure and `tox` environments.
