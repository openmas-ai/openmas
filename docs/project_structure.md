# OpenMAS Project Structure

OpenMAS promotes a standardized project structure to enhance organization, maintainability, and collaboration in Multi-Agent System (MAS) development. This structure is automatically generated when you use the `openmas init` command.

## Standard Directory Layout

A typical OpenMAS project, initialized via `openmas init your_mas_project_name`, looks like this:

    your_mas_project_name/
    ├── agents/              # Code for individual agents/components
    │   ├── <agent_name_1>/
    │   │   ├── agent.py          # BaseAgent subclass implementation
    │   │   ├── requirements.txt  # Optional: Agent-specific deps (rarely needed)
    │   │   └── openmas.deploy.yaml # Optional: Deployment hints for this agent
    │   └── <agent_name_2>/
    │       └── ...
    ├── extensions/          # Project-local OpenMAS extensions
    │   └── my_custom_comm/
    │       └── communicator.py   # Example: Custom BaseCommunicator subclass
    ├── shared/              # Project-internal shared Python code
    │   └── utils.py           # Example: Utility functions used by multiple agents
    ├── packages/            # Installed external OpenMAS packages (Git ignored)
    │   └── openmas_kafka/     # Example: Content of an installed package
    ├── config/              # Environment-specific config files
    │   ├── default.yml        # Base configuration
    │   └── production.yml     # Example: Production environment overrides
    ├── tests/               # Project/Application-level tests
    │   └── test_integration.py
    ├── .env                 # Optional: Local environment variables (Git ignored)
    ├── .gitignore           # Standard git ignore file
    ├── openmas_project.yml  # Central project configuration (Required)
    ├── requirements.txt     # Top-level Python dependencies (incl. openmas framework)
    └── README.md            # Project description

## Core Directory Roles

* **`agents/`**:
    * **Purpose:** Contains the primary logic for each distinct agent or component in the MAS. Each subdirectory typically represents one runnable agent instance.
    * **Contents:** Inside each `<agent_name>/` directory, the key file is `agent.py`, which must contain a class inheriting from `openmas.agent.BaseAgent`. It might also contain helper modules specific to that agent, optional agent-specific Python dependencies (`requirements.txt`, though uncommon), and an optional `openmas.deploy.yaml` for deployment hints.
    * **Registration:** Agents defined here must be registered in the `agents:` section of `openmas_project.yml` to be recognized by the `openmas run` command.

* **`extensions/`** (Local Extensions):
    * **Purpose:** Holds project-specific Python code that extends or customizes the OpenMAS framework *locally* within this project. This is the place for custom `BaseCommunicator` subclasses, specialized `BaseAgent` types tailored to this project, reusable patterns specific to this MAS, or utility functions tightly coupled to the framework's extension points used *only* in this project.
    * **Nature:** Code written directly within this project, not intended for easy sharing across different MAS projects without copying.
    * **Discovery:** The framework finds code here based on the directories listed in `extension_paths` in `openmas_project.yml`. These paths are added to `sys.path` during execution (e.g., by `openmas run`), making modules within importable. Framework mechanisms (like communicator lookup) search within these paths.

* **`shared/`**:
    * **Purpose:** Contains general-purpose Python code (utility functions, data models/schemas defined with Pydantic, constants, business logic helpers) that needs to be shared between multiple *local* components within the *same project*. For instance, code used by several agents in the `agents/` directory or by code within `extensions/`.
    * **Nature:** Project-internal library code. Not directly extending the framework, but providing common functionality for the application's components.
    * **Discovery:** The framework finds code here based on the directories listed in `shared_paths` in `openmas_project.yml`. These paths are added to `sys.path` during execution, allowing agents and extensions to import modules from `shared/`.

* **`packages/`** (External Packages):
    * **Purpose:** Contains reusable OpenMAS components (communicators, agents, patterns) developed externally and installed into the project as dependencies. This directory is managed by the `openmas deps` command based on the `dependencies:` section in `openmas_project.yml`.
    * **Nature:** Shareable, often versioned code fetched from external sources (currently Git repositories. Planned: local paths and the OpenMAS package hub). This directory should typically be added to `.gitignore`, as dependencies should be fetched declaratively via `openmas deps`.
    * **Discovery:** The framework searches within the installed package directories (specifically configured subdirectories within it, often `src/` or the root) for components (e.g., communicators defined via entry points or convention) and adds relevant paths to `sys.path`.

* **`config/`**:
    * **Purpose:** Stores environment-specific configuration files (YAML format). See the [Configuration Guide](guides/configuration.md).
    * **Contents:** Typically includes `default.yml` (base configuration) and files for different environments like `local.yml`, `development.yml`, `production.yml`.

* **`tests/`**:
    * **Purpose:** Contains project-level tests (unit, integration) for your agents and shared code. These are distinct from the internal tests used for [developing the OpenMAS framework itself](contributing.md).

## Central Configuration (`openmas_project.yml`)

This required YAML file resides at the project root and defines the overall structure and metadata for your OpenMAS project.

```yaml
# Example openmas_project.yml
name: "my_mas_project"        # Project name (used by CLI, logging)
version: "0.1.0"              # Project version

# Defines the agents in the system and their locations
agents:
    orchestrator: "agents/orchestrator" # Maps logical name 'orchestrator' to its code path
    data_fetcher: "agents/fetcher"
    analyzer: "agents/analyzer"

# List of directories containing shared Python code used by agents/extensions
shared_paths:
    - "shared/utils"
    - "shared/models"

# List of directories containing project-local framework extensions
extension_paths:
    - "extensions"

# Defines external OpenMAS package dependencies (managed by `openmas deps`)
dependencies:
    - git: https://github.com/some_org/openmas-kafka-comm.git
    revision: v1.2.0 # Can be a tag, branch, or commit hash
    # - package: vendor/some-pattern # Future: PyPI-like packages
    #   version: ">=1.0,<2.0"
    # - local: ../shared-openmas-components # Future: Local path dependencies

# Default configuration values (lowest precedence)
default_config:
    log_level: "INFO"
    communicator_type: "http"
    communicator_options:
    timeout: 30
    # Other default parameters accessible via agent.config
    default_retry_attempts: 3
```

**Key Sections:**

* **`name`**: The name of your MAS project.
* **`version`**: The version of your project.
* **`agents`**: A mapping where keys are the logical names used to refer to agents (e.g., in `openmas run orchestrator` or in `service_urls`) and values are the relative paths to the agent's code directory from the project root.
* **`shared_paths`**: A list of relative paths (from the project root) to directories containing shared Python modules accessible by agents and extensions.
* **`extension_paths`**: A list of relative paths to directories containing project-local framework extensions (like custom communicators or base agents).
* **`dependencies`**: A list defining external OpenMAS package dependencies. Currently supports `git` dependencies with an optional `revision`. Used by the `openmas deps` command to populate the `packages/` directory.
* **`default_config`**: A dictionary containing default configuration parameters that apply to all agents in the project. These have the lowest precedence in the configuration layering. See [Configuration Guide](guides/configuration.md).

## How Components Interact

When a command like `openmas run <agent_name>` executes:

1.  It finds the project root and parses `openmas_project.yml`.
2.  It identifies the target agent's path from the `agents:` section.
3.  It determines the paths from `shared_paths` and `extension_paths`.
4.  It identifies installed packages in the `packages/` directory (based on `dependencies:` metadata).
5.  It constructs the Python `sys.path` to include the agent's directory, shared paths, extension paths, and relevant paths within installed packages.
6.  It loads the agent code (`agent.py`), which can now successfully `import` modules from `shared/`, `extensions/`, and installed `packages/`.
7.  Framework mechanisms, like the communicator lookup based on `communicator_type`, search across built-in components, then `extension_paths`, then installed `packages/`.

The `openmas_project.yml` serves as the root-level configuration file that defines the project structure, agent entry points, dependencies, and the primary reference in the configuration layering. See [Configuration Guide](guides/configuration.md).
