# Contributing to Hypomnemata

Thank you for your interest in contributing to Hypomnemata! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/byrondenham/hypomnemata.git
cd hypomnemata

# Create a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev,api,watch]"
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=hypomnemata --cov-report=term-missing

# Run specific test file
pytest tests/test_sqlite_index.py

# Run tests in quiet mode
pytest -q
```

### Linting

We use `ruff` for linting and code formatting:

```bash
# Check code style
ruff check src tests

# Auto-fix issues where possible
ruff check --fix src tests
```

### Type Checking

We use `mypy` for static type checking:

```bash
# Type check the source code
mypy src
```

### Running the Full Quality Check

```bash
# Run lint, type check, and tests
ruff check src tests && mypy src && pytest
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use descriptive variable and function names
- Add docstrings for public functions and classes

## Commit Guidelines

- Write clear, concise commit messages
- Use the imperative mood ("Add feature" not "Added feature")
- Reference issue numbers when applicable (e.g., "Fix #123")
- Keep commits focused on a single change

Example commit message:
```
Add support for custom metadata namespaces

- Implement namespace validation
- Add tests for namespace parsing
- Update documentation

Fixes #42
```

## Pull Request Process

1. Fork the repository and create a new branch from `main`
2. Make your changes, ensuring tests pass
3. Update documentation if needed
4. Run linting and type checking
5. Submit a pull request with a clear description of changes
6. Address any review feedback

## Testing Guidelines

- Write tests for new features and bug fixes
- Maintain or improve code coverage
- Test edge cases and error conditions
- Use descriptive test names that explain what is being tested

Example test structure:
```python
def test_feature_handles_edge_case():
    """Test that feature correctly handles empty input."""
    result = my_function("")
    assert result == expected_value
```

## Documentation

- Update README.md for user-facing changes
- Update CLI_DEMO.md for new CLI commands
- Add docstrings to new functions and classes
- Update CHANGELOG.md following Keep a Changelog format

## Adding Dependencies

- Add runtime dependencies to `dependencies` in `pyproject.toml`
- Add development dependencies to `dev` optional dependencies
- Keep dependencies minimal and well-justified
- Pin minimum versions, not maximum versions

## Release Process

See [RELEASING.md](RELEASING.md) for the release process (maintainers only).

## Getting Help

- Open an issue for bug reports or feature requests
- Check existing issues before creating a new one
- Be respectful and constructive in discussions

## License

By contributing to Hypomnemata, you agree that your contributions will be licensed under the MIT License.
