# OpenMAS Package Management

OpenMAS supports external package management through the `openmas deps` command, inspired by dbt's package management system. This allows you to include external Git repositories as dependencies in your OpenMAS project.

## Configuration

Dependencies are defined in the `dependencies` section of your `openmas_project.yml` file:

```yaml
dependencies:
  - git: https://github.com/example/openmas-repo.git
    revision: main  # Optional: branch, tag, or commit hash
```

## Supported Dependency Types

Currently, OpenMAS supports the following dependency types:

### Git Dependencies (Implemented)

Git dependencies allow you to include code from Git repositories:

```yaml
dependencies:
  - git: https://github.com/example/repo.git
    revision: main  # Optional: branch, tag, or commit
```

- The `git` key specifies the Git repository URL
- The optional `revision` key specifies a branch, tag, or commit to checkout

### Package Dependencies (Not Yet Implemented)

Package dependencies will allow importing from centralized package repositories:

```yaml
dependencies:
  - package: example/package-name
    version: 1.0.0
```

### Local Dependencies (Not Yet Implemented)

Local dependencies will allow referencing code from other directories:

```yaml
dependencies:
  - local: ../path/to/local/package
```

## Installing Dependencies

To install or update the dependencies defined in your project, run:

```bash
openmas deps
```

This will:
1. Create a `packages/` directory in your project (if it doesn't exist)
2. Clone Git repositories to `packages/<repo-name>`
3. Checkout the specified revision (branch, tag, or commit)

### Options

- `--project-dir PATH`: Specify the project directory containing `openmas_project.yml`
- `--clean`: Clean (remove) the packages directory before installing dependencies

## Usage in Your Project

Code from installed packages is automatically available to your agents. When running an agent with `openmas run`, the system automatically adds:

- The package's `src/` directory to the Python path (if it exists)
- Otherwise, the package's root directory

This means you can import modules from installed packages directly in your agent code:

```python
# If the package has a src/ directory
from package_name.module import something

# If the package doesn't have a src/ directory
from module import something
```

## Validating Dependencies

To validate the dependency configuration in your project:

```bash
openmas validate
```

This checks that:
- Each dependency has a valid type (`git`, `package`, or `local`)
- Git dependencies have valid URLs
- Package dependencies have the required `version` field

## Best Practices

1. Always specify a `revision` for Git dependencies to ensure reproducibility
2. Consider using the `.gitignore` file to exclude the `packages/` directory (OpenMAS init does this by default)
3. Use `openmas deps` in your CI/CD pipelines to ensure dependencies are properly installed
