# Contributing to OpenMAS

We welcome contributions to OpenMAS! Whether you're fixing a bug, improving documentation, or proposing a new feature, your help is appreciated.

Please follow standard GitHub practices:

1.  **Fork the repository.**
2.  **Create a new branch** for your changes (`git checkout -b feature/my-new-feature` or `bugfix/issue-number`).
3.  **Make your changes.** Ensure you follow the project's coding style and conventions.
4.  **Add tests** for any new features or bug fixes.
5.  **Ensure all tests pass** by running `tox`.
6.  **Update documentation** if necessary.
7.  **Submit a Pull Request** against the `main` branch.

## Development Setup

Please refer to the [main README](https://github.com/dylangames/openmas/blob/main/README.md#development) for instructions on setting up your development environment using Poetry and pre-commit hooks.

## Code Style and Quality

We use `black` for formatting, `isort` for import sorting, `flake8` for linting, and `mypy` for type checking. These are enforced via pre-commit hooks.

### Docstrings

Clear and consistent docstrings are important. Please adhere to the guidelines outlined in our [Docstring Policy](docstring_policy.md).

## Testing

All contributions must include relevant tests. Please follow the testing strategy outlined in the [Testing README](https://github.com/dylangames/openmas/blob/main/tests/README.md).

Run tests using `tox`:

```
