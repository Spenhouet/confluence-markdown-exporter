# Contributing

Any contribution is welcome! This document provides guidelines for contributing to the confluence-markdown-exporter project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Release Process](#release-process)
- [Pull Request Guidelines](#pull-request-guidelines)

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- `uv` (Python package manager)
- `jq` (for JSON processing)

### Install jq

```bash
sudo apt-get install jq
```

### Install `uv`

Following the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Add shell completion (optional):

```bash
echo 'eval "$(uv generate-shell-completion bash)"' >> ~/.bashrc
```

### Project Setup

1. **Fork and Clone the Repository**

   ```bash
   git clone https://github.com/Spenhouet/confluence-markdown-exporter.git
   cd confluence-markdown-exporter
   ```

2. **Install Dependencies**

   ```bash
   uv sync --all-groups
   ```

   This will:

   - Create a virtual environment
   - Install all dependencies (including development dependencies via dependency groups)
   - Install the project in editable mode

3. **Verify Installation**

   ```bash
   uv run confluence-markdown-exporter --help
   uv run cf-export --help
   ```

## Development Workflow

### Running the Application

```bash
# Run with uv (recommended)
uv run confluence-markdown-exporter [commands]
uv run cf-export [commands]

# Or activate the virtual environment
source .venv/bin/activate
confluence-markdown-exporter [commands]
```

### Adding Dependencies

```bash
# Add runtime dependency
uv add package-name

# Add development dependency (to dev group)
uv add --group dev package-name

# Add to custom dependency group
uv add --group group-name package-name
```

### Updating Dependencies

```bash
# Update all dependencies
uv sync --upgrade

# Update specific dependency
uv sync --upgrade-package package-name
```

## Testing

We use `pytest` for testing. Tests are located in the `tests/` directory.

### Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_basic.py

# Run specific test
uv run pytest tests/test_basic.py::test_package_imports
```

### Writing Tests

1. **Create test files** in the `tests/` directory with the prefix `test_`
2. **Follow naming conventions**: `test_*.py` files, `test_*` functions
3. **Use descriptive test names** that explain what is being tested
4. **Add docstrings** to explain complex test scenarios

Example test structure:

```python
def test_feature_description() -> None:
    """Test that the feature works as expected."""
    # Arrange
    input_data = "test input"

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_output
```

## Code Quality

### Linting with Ruff

We use `ruff` for Python linting and code formatting.

```bash
# Check code quality
uv run ruff check

# Auto-fix issues where possible
uv run ruff check --fix

# Check specific files or directories
uv run ruff check confluence_markdown_exporter/
uv run ruff check tests/
```

### Code Style Guidelines

- **Line length**: Maximum 100 characters
- **Docstring style**: Google docstring convention
- **Import formatting**: One import per line (enforced by ruff)
- **Type hints**: Use type annotations for new code

### Pre-commit Workflow

Before committing:

1. **Run linting**: `uv run ruff check`
2. **Run tests**: `uv run pytest`
3. **Fix any issues** before committing

## Release Process

> [!NOTE]
> Only relevant for maintainers.

### Automated Release

We use GitHub Actions for automated releases:

1. **Trigger Release Workflow**

   - Go to GitHub Actions tab
   - Run "Release" workflow
   - Choose version bump type (patch/minor/major) or specify custom version

2. **Automated Steps**
   - Updates version in `pyproject.toml`
   - Runs tests and builds
   - Creates Git tag
   - Publishes to PyPI
   - Creates GitHub release with auto-generated notes

## Pull Request Guidelines

### Before Submitting

1. **Create a feature branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Run the full test suite**

   ```bash
   uv run ruff check
   uv run pytest
   uv build --no-sources  # Test build
   ```

3. **Update documentation** if needed

### PR Requirements

- ✅ **All tests pass** (verified by CI)
- ✅ **Code passes linting** (ruff check)
- ✅ **Descriptive PR title** and description
- ✅ **Reference related issues** if applicable
- ✅ **Update tests** for new functionality
- ✅ **Update documentation** for user-facing changes

## Development Environment

### Recommended Tools

- **IDE**: VS Code with Python extension
- **Git client**: Command line or your preferred GUI
- **Terminal**: Any modern terminal with shell completion

### VS Code Extensions

Recommended extensions for development:

- Python (Microsoft)
- Ruff (Astral Software)
- GitLens (GitKraken)
- markdownlint (David Anson)

### Project Structure

```text
confluence-markdown-exporter/
├── .github/workflows/      # CI/CD workflows
├── confluence_markdown_exporter/  # Main package
│   ├── __init__.py
│   ├── main.py            # CLI entry point
│   ├── confluence.py      # Core functionality
│   ├── api_clients.py     # API integrations
│   └── utils/             # Utility modules
├── tests/                 # Test suite
├── .ruff.toml            # Ruff configuration
├── pyproject.toml        # Project configuration
├── uv.lock              # Dependency lock file
└── CONTRIBUTING.md       # This file
```

## Getting Help

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Documentation**: Check the README and code comments

Thank you for contributing to confluence-markdown-exporter! 🚀
