# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2]

### Added

- **Enhanced Asset Management:**
  - **Automatic .env Loading:** Detects and loads environment variables from `.env` file for all CLI commands
  - **Secure Authentication:** Added support for authentication with gated assets (Hugging Face Hub, HTTP)
  - **Configurable Retries:** Improved download reliability with customizable retry mechanism
  - **Progress Reporting:** Added visual progress bars and interval logging for downloads
  - **Force Download Option:** Added `--force` flag to CLI for re-downloading cached assets
  - **Cache Control Commands:** Enhanced CLI commands for cache management

### Changed

- **Documentation:** Updated guides for asset management, configuration, and CLI
- **Dependency Management:** Added `python-dotenv` as a core dependency

### Future Improvements

- **Test Coverage:** Overall test coverage is at ~70%, with key modules needing additional tests:
  - The next release should include additional test cases to reach the new 80% target coverage

## [0.2.1]

### Fixed

- Correct openmas toml and cli version logic (#86).


## [0.2.0]

### Added

- **Asset Management:** A robust system for managing external assets required by agents:
  - Declarative asset configuration in `openmas_project.yml`
  - Automatic caching, downloading, and verification of assets
  - Support for multiple source types (HTTP, Hugging Face Hub, local)
  - Checksum verification for integrity checking
  - Archive unpacking support
  - CLI commands for asset management (`openmas assets`)

- **Prompt Management:** A comprehensive prompt template management system:
  - Configuration-based prompt definitions
  - Template interpolation with variables
  - Support for file-based and inline templates
  - Centralized prompt registry
  - Runtime prompt rendering
  - CLI commands for prompt management (`openmas prompts`)

- **Sampling Configuration:** Flexible LLM sampling configuration framework:
  - Provider-agnostic sampling parameters
  - Integration with MCP and mock providers
  - Agent-level sampling configuration
  - Support for various sampling parameters (temperature, top_p, etc.)
  - Control over model selection and generation parameters

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
