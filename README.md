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

**Source Code**: <a href="https://github.com/yanga-project/yanga-core" target="_blank">https://github.com/yanga-project/yanga-core</a>

---

Core library for C/C++ software product line (SPL) engineering. Works with any build system.

Yanga Core provides data models, configuration loading, pipeline steps, and commands that build system integrations (like [Yanga](https://github.com/yanga-project/yanga) for CMake) use to:

- Define platforms, variants, and components for a product line
- Run build pipeline steps (KConfig generation, dependency installation, static analysis, ...)
- Generate HTML reports (CppCheck, Sphinx docs, coverage)

## Installation

Requires Python 3.10+.

```bash
pip install yanga-core
```

## Quick Start

`yanga-core` is a library, not a standalone CLI. Applications import its modules and compose them. See [Yanga](https://github.com/yanga-project/yanga) for a CMake-based application built on `yanga-core`.

```python
from pathlib import Path
from yanga_core.domain.project_slurper import YangaProjectSlurper

slurper = YangaProjectSlurper(project_dir=Path("."))
for variant in slurper.variants:
    print(f"Variant: {variant.name}, components: {variant.components}")
```

## Documentation

Full documentation is available in the [docs/](docs/) directory:

- **[Tutorials](docs/tutorials/)** — learn yanga-core step-by-step
- **[How-to Guides](docs/how-to/)** — task-oriented guides for specific goals
- **[Reference](docs/reference/)** — configuration, domain model, pipeline, and API
- **[Explanation](docs/explanation/)** — architecture, design decisions, and concepts

## Contributing

See the [Contributing Guide](docs/how-to/contributing.md) for setup instructions, running tests, and code quality standards.

## Credits

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

This package was created with
[Copier](https://copier.readthedocs.io/) and the
[browniebroke/pypackage-template](https://github.com/browniebroke/pypackage-template)
project template.
