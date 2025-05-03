# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]

### Added

-   **Core Agent Framework:** Introduced `BaseAgent` with an asynchronous lifecycle (`setup`, `run`, `shutdown`) for simplified agent development.
-   **Pluggable Communication Layer:** Support for various protocols (HTTP, MCP, gRPC, MQTT) via lazy-loaded communicators, enabling flexible integration and extension.
-   **Project Scaffolding:** `openmas init` command to generate standardized project structures.
-   **Layered Configuration System:** Load settings from YAML files, `.env`, and environment variables.
-   **Reasoning Agnosticism:** Base support for heuristic logic with clear pathways for integrating LLMs and BDI patterns.
-   **CLI Tool Suite:** Initial `openmas` CLI commands for project initialization (`init`), configuration validation (`validate`), local execution (`run`), dependency management (`deps`), and deployment artifact generation (`generate-dockerfile`, `generate-compose`).
-   **Testing Utilities:** Included `MockCommunicator` and `AgentTestHarness` for facilitating unit and integration testing.
-   **Initial Documentation:** Comprehensive guides and API reference covering core concepts, features, and usage.

### Notes
- Initial support for MQTT (`MqttCommunicator`) and gRPC (`GrpcCommunicator`) is included but considered **experimental** in this release. These components have limited testing and potentially unstable APIs, and are not recommended for production use at this time.
