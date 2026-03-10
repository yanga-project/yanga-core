# Contributing

How to set up a development environment and contribute to yanga-core.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (package manager)
- [pypeline-runner](https://github.com/cuinixam/pypeline) (automation)

## Setup

```bash
# Clone the repository
git clone https://github.com/yanga-project/yanga-core.git
cd yanga-core

# Install dependencies
uv sync
```

## Running Tests

The project uses `pypeline-runner` for all automation:

```bash
# Run full pipeline (lint + tests) — this is the primary verification command
pypeline run

# Run only linting (pre-commit hooks)
pypeline run --step PreCommit

# Run only tests with a specific Python version
pypeline run --step CreateVEnv --step PyTest --single --input python_version=3.13
```

## Code Quality

- [Ruff](https://github.com/astral-sh/ruff) handles linting and formatting (configured in `pyproject.toml`)
- [pre-commit](https://pre-commit.com/) hooks enforce code standards automatically
- Type hints are required (`py.typed` marker is present)
- Commits must follow [conventional commits](https://www.conventionalcommits.org)

See {doc}`/reference/coding-guidelines` for the full coding standards.

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. **Lint** (`PreCommit` step) — Ruff linting/formatting via pre-commit
2. **Commit Lint** — enforces conventional commits
3. **Test** — matrix: Python 3.10 & 3.13 on Ubuntu, Windows, and macOS
4. **Release** — semantic versioning with automatic PyPI publishing

## Definition of Done

Changes are not complete until:

- `pypeline run` executes with **zero failures**
- **All new functionality has tests** — never skip writing tests for new code
- Test coverage includes edge cases and error conditions

## Dependencies

| Category | Tools |
|----------|-------|
| **Core** | `typer`, `mashumaro`, `py-app-dev`, `clanguru`, `kspl`, `pick` |
| **Build** | `pypeline-runner`, `uv` |
| **Dev** | `pytest`, `ruff`, `pre-commit` |
