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
   uv run cme --help
   ```

## Development Workflow

### Running the Application

```bash
# Run with uv (recommended)
uv run confluence-markdown-exporter [commands]
uv run cme [commands]

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
   - Builds and pushes the multi-arch Docker image to Docker Hub (triggered by the version tag)

### Docker Image Publishing

The `Build and publish Docker image` workflow (`.github/workflows/docker.yml`) is split into two jobs:

- `build` – runs on every trigger (including pull requests) using the official Docker actions (`docker/setup-qemu-action`, `docker/setup-buildx-action`, `docker/build-push-action`) to build the image for `linux/amd64` and `linux/arm64`. **No push, no secrets accessed.** This validates Dockerfile changes from contributors.
- `publish` – runs only on `push` and `workflow_dispatch` events (skipped for pull requests), depends on `build`, and is bound to the `dockerhub` GitHub environment which holds the credentials. Adds `docker/login-action` and `docker/metadata-action`, then pushes with `docker/build-push-action`.

Trigger summary:

- pushes to `main` (publishes `main` and `sha-<short>` tags)
- pushes of version tags such as `5.1.0` (publishes `5.1.0`, `5.1`, `5`, and `latest`)
- pull requests touching the image or its inputs (build job only — does **not** push and does **not** require Docker Hub secrets)
- manual `workflow_dispatch`

#### One-time Docker Hub setup (maintainer)

Docker Hub credentials live on a dedicated GitHub **environment** named `dockerhub` (analogous to how PyPI publishing uses the `release` environment). Repository-level secrets are *not* used. Set this up once:

1. **Create the Docker Hub repository** at <https://hub.docker.com/repositories> — by default the workflow pushes to `spenhouet/confluence-markdown-exporter`. If you use a different namespace or name, set the repository variable `DOCKERHUB_IMAGE` (see step 5).
2. **Create a Docker Hub access token** at <https://app.docker.com/settings/personal-access-tokens> with `Read, Write, Delete` scope. Treat it like a password.
3. **Create the `dockerhub` environment** in GitHub: Settings → Environments → *New environment* → name it `dockerhub`. Optionally configure:
   - **Deployment branches and tags** → *Selected branches and tags* → add `main` and the tag pattern `*.*.*` so the environment can only be entered from those refs.
   - **Required reviewers** if you want a manual approval gate before any image is pushed (not required for an automated flow).
4. **Add environment secrets** (within the `dockerhub` environment you just created → *Add environment secret*):
   - `DOCKERHUB_USERNAME` – your Docker Hub account name (the namespace owner, not an email).
   - `DOCKERHUB_TOKEN` – the access token from step 2.
5. **(Optional) Override the image name** by adding a repository *variable* (Settings → Secrets and variables → Actions → *Variables* tab) named `DOCKERHUB_IMAGE` with the fully qualified image name, e.g. `myorg/confluence-markdown-exporter`. An environment-level variable would also work; the repository scope is just simpler since the image name is not a secret.

Once the environment and its secrets exist, the next push to `main` or version tag will publish the image. Each publish appears under the repository's **Deployments → dockerhub** view, mirroring the PyPI release deployment history.

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
