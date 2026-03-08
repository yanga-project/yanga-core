# Yanga Core

<p align="center">
  <a href="https://github.com/yanga-project/yanga-core/actions/workflows/ci.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/yanga-project/yanga-core/ci.yml?branch=main&label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://codecov.io/gh/yanga-project/yanga-core">
    <img src="https://img.shields.io/codecov/c/github/yanga-project/yanga-core.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
  </a>
  <a href="https://github.com/cuinixam/pypeline">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cuinixam/pypeline/refs/heads/main/assets/badge/v0.json" alt="pypeline">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/yanga-core/">
    <img src="https://img.shields.io/pypi/v/yanga-core.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/yanga-core.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/yanga-core.svg?style=flat-square" alt="License">
</p>

---

**Source Code**: <a href="https://github.com/yanga-project/yanga-core" target="_blank">https://github.com/yanga-project/yanga-core </a>

---

Core library for C/C++ software product line (SPL) engineering. Works with any build system.

Yanga Core provides data models, configuration loading, pipeline steps, and commands that build system integrations (like [Yanga](https://github.com/yanga-project/yanga) for CMake) use to:

- Define platforms, variants, and components for a product line
- Run build pipeline steps (KConfig generation, dependency installation, static analysis, ...)
- Generate HTML reports (CppCheck, Sphinx docs, coverage)

## Key Concepts

- **Platform** — build target with generators and build types (Debug, Release, ...)
- **Variant** — product configuration that picks which components to build for a platform
- **Component** — source code unit with sources, tests, docs, and include directories
- **ExecutionContext** — holds the active variant, platform, components, and shared data registry
- **Pipeline Step** — one step in the build pipeline (e.g. KConfig generation, dependency installation)

## Installation

Requires Python 3.10+.

```bash
pip install yanga-core
```

## Usage

`yanga-core` is a library, not a standalone CLI. Applications import its modules and compose them. See [Yanga](https://github.com/yanga-project/yanga) for a CMake-based application using `yanga-core`.

```python
from yanga_core.domain.config import PlatformConfig, VariantConfig
from yanga_core.domain.components import Component
from yanga_core.domain.execution_context import ExecutionContext, UserRequest, UserRequestScope
from yanga_core.domain.project_slurper import ProjectSlurper
```

### Core Modules

| Module                | Description                                                                |
| --------------------- | -------------------------------------------------------------------------- |
| `yanga_core.domain`   | Config models, components, execution context, artifacts                    |
| `yanga_core.commands` | Commands for running steps, reports, compile commands, CppCheck, HTML fixes |
| `yanga_core.steps`    | Pipeline steps for `pypeline` (KConfig, dependency install, reports)       |
| `yanga_core.docs`     | Sphinx doc generation helpers                                              |

## Contributing

### Setup

```bash
# Clone the repository
git clone https://github.com/yanga-project/yanga-core.git
cd yanga-core

# Install dependencies (using uv)
uv sync
```

### Running Tests

The project uses [pypeline-runner](https://github.com/yanga-project/pypeline) for automation:

```bash
# Run full pipeline (lint + tests)
pypeline run

# Run only linting
pypeline run --step PreCommit

# Run only tests with a specific Python version
pypeline run --step CreateVEnv --step PyTest --single --input python_version=3.13
```

### Code Quality

- [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- [pre-commit](https://pre-commit.com/) hooks enforce code standards
- Commits must follow [conventional commits](https://www.conventionalcommits.org)

## Credits

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

This package was created with
[Copier](https://copier.readthedocs.io/) and the
[browniebroke/pypackage-template](https://github.com/browniebroke/pypackage-template)
project template.
