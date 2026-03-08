# Yanga Core Development Guide for AI Agents

## Project Overview

Yanga Core is the core library for C/C++ software product line (SPL) engineering. It provides data models, configuration loading, pipeline steps, and commands that any build system integration can use. For example, [Yanga](https://github.com/yanga-project/yanga) uses it for CMake builds, but another application could use `yanga_core` to target Ninja, Maven, or any other build system.

### Key Concepts

- **Platform** (`PlatformConfig`) — build target with generators and build types (Debug, Release, ...)
- **Variant** (`VariantConfig`) — product configuration that picks which components to build for a platform
- **Component** (`Component`) — source code unit with sources, tests, docs, and include directories
- **ExecutionContext** — holds the active variant, platform, components, user request, and a data registry (artifacts, report files)
- **UserRequest** — what the user wants to do (scope: variant/component, target: build/test/coverage/report, build type)
- **Artifact** — build output (file or directory) with provider/consumer tracking
- **Pipeline Step** — one step in the build pipeline (e.g. KConfig generation, dependency installation, report generation)

### Architecture

`yanga_core` is a library, not a standalone CLI. Applications import its modules and compose them:

- **Command classes** (`yanga_core.commands`) — command implementations that applications register with their own CLI
- **Domain objects** (`yanga_core.domain`) — config models, component analysis, execution context, and artifact tracking
- **Pipeline steps** (`yanga_core.steps`) — steps for `pypeline` pipelines
- **ExecutionContext** — dependency container that generators and steps use to access project state and shared data

[Yanga](https://github.com/yanga-project/yanga) (CMake-based builds) is one example of an application built on top of `yanga_core`.

### Project Structure

```text
src/yanga_core/
├── commands/       # Reusable command classes
│   ├── base.py                      # Base command class
│   ├── run.py                       # RunCommand — run a pipeline step
│   ├── report_config.py             # ReportConfigCommand — generate report configuration
│   ├── filter_compile_commands.py   # FilterCompileCommandsCommand — component-scoped compile_commands.json
│   ├── cppcheck_report.py           # CppCheckReportCommand — CppCheck XML to HTML
│   └── fix_html_links.py            # FixHtmlLinksCommand — fix Sphinx HTML links
├── domain/         # Core data models and business logic
│   ├── config.py             # Configuration dataclasses (YangaUserConfig, VariantConfig, PlatformConfig, ComponentConfig)
│   ├── components.py         # Component runtime representation
│   ├── execution_context.py  # ExecutionContext, UserRequest, UserRequestScope
│   ├── project_slurper.py    # Project discovery and configuration loading
│   ├── artifact.py           # Artifact management with provider/consumer tracking
│   ├── spl_paths.py          # Path resolution for build directories
│   ├── reports.py            # Report data structures (ReportRelevantFiles, ReportData)
│   ├── config_slurper.py     # YAML configuration file loading
│   ├── config_utils.py       # Configuration utility helpers
│   ├── component_analyzer.py # Source/test/docs file collection utilities
│   └── generated_file.py     # File generation interface
├── docs/           # Sphinx documentation generation utilities
├── steps/          # Pipeline step implementations
│   ├── kconfig_gen.py           # KConfig generation
│   ├── generate_report_config.py # Report configuration generation
│   ├── west_install.py          # West dependency installation
│   ├── scoop_install_base.py    # Scoop installation base class
│   ├── scoop_install.py         # Scoop dependency installation
│   └── poks_install.py          # Poks dependency installation
└── ini.py          # Project-level configuration loader (yanga.ini / pyproject.toml [tool.yanga])
```

### Commands

These are command classes consumed by the `yanga` CLI — not standalone entry points:

- **`RunCommand`** — runs a pipeline step (with dependencies) for a given platform/variant
- **`ReportConfigCommand`** — generates report configuration per component
- **`FilterCompileCommandsCommand`** — creates a component-scoped `compile_commands.json`
- **`CppCheckReportCommand`** — converts CppCheck XML to HTML
- **`FixHtmlLinksCommand`** — fixes broken links in Sphinx HTML output

## Development Guidelines

### ⚠️ MANDATORY: Plan Before Execution

**NEVER start making changes without presenting a plan first.** This is a critical rule.

1. **Create an implementation plan** documenting:
   - What files will be modified, created, or deleted
   - What changes will be made and why
   - How the changes will be verified
2. **Present the plan for user review** and ask for approval
3. **Wait for explicit approval** before proceeding with any file modifications
4. **Only after approval**, begin execution

Skipping this step is unacceptable.

### ⚠️ MANDATORY: Never Change the Plan Without Approval

**NEVER deviate from the approved plan without asking the user first.** If the current approach hits a blocker (e.g., a tool doesn't work, a dependency is missing, a test fails unexpectedly), you MUST:

1. **Stop** — do not attempt an alternative approach on your own
2. **Report the problem** to the user with a clear description of what went wrong
3. **Propose alternatives** if you have ideas, but do NOT implement them
4. **Wait for explicit approval** before changing direction

This applies to all scope changes: switching libraries, replacing test targets, altering architecture, or any deviation from what was agreed upon. The user decides, not the agent.

### Running Tests and Verification

The project uses `pypeline-runner` for all automation. Key commands:

```bash
# Run full pipeline (lint + tests) - this is the primary verification command
pypeline run

# Run only linting (pre-commit hooks)
pypeline run --step PreCommit

# Run only tests with specific Python version
pypeline run --step CreateVEnv --step PyTest --single --input python_version=3.13
```

### CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. **Lint** (`PreCommit` step) - Runs ruff linting/formatting via pre-commit
2. **Commit Lint** - Enforces [conventional commits](https://www.conventionalcommits.org)
3. **Test** - Matrix: Python 3.10 & 3.13 on Ubuntu, Windows, and macOS
4. **Release** - Semantic versioning with automatic PyPI publishing

### Code Quality

- **Ruff** handles linting/formatting (configured in `pyproject.toml`)
- **Pre-commit hooks** enforce code standards
- **Type hints** are required (`py.typed` marker present)
- Docstrings follow standard conventions but are not required for all functions

### Dependencies

- **Core**: `typer` (CLI), `mashumaro` (serialization), `py-app-dev` (utilities), `clanguru` (C/C++ tooling), `kspl` (KConfig/SPL), `pick` (interactive selection)
- **Build**: `pypeline-runner` (automation), `uv` (package management and builds)
- **Dev**: `pytest` (testing), `ruff` (linting, formatting), `pre-commit` (hooks)

## Coding Guidelines

- **Less is more** — be concise and question every implementation that looks too complicated; if there is a simpler way, use it.
- **Never nester** — maximum three indentation levels are allowed. Use early returns, guard clauses, and extraction into helper functions to keep nesting shallow. The third level should only be used when truly necessary.
- **Use dataclasses for complex data structures**: Prefer using `dataclasses` over complex standard types (e.g. `tuple[list[str] | None, dict[str, str] | None]`) for function return values or internal data exchange to improve readability and extensibility.
- Always include full **type hints** (functions, methods, public attrs, constants).
- Prefer **pythonic** constructs: context managers, `pathlib`, comprehensions when clear, `enumerate`, `zip`, early returns, no over-nesting.
- Follow **SOLID**: single responsibility; prefer composition; program to interfaces (`Protocol`/ABC); inject dependencies.
- **Naming**: descriptive `snake_case` vars/funcs, `PascalCase` classes, `UPPER_SNAKE_CASE` constants. Avoid single-letter identifiers (including `i`, `j`, `a`, `b`) except in tight math helpers.
- Code should be **self-documenting**. Use docstrings only for public APIs or non-obvious rationale/constraints; avoid noisy inline comments.
- Errors: raise specific exceptions; never `except:` bare; add actionable context.
- Imports: no wildcard; group stdlib/third-party/local, keep modules small and cohesive.
- Testability: pure functions where possible; pass dependencies, avoid globals/singletons.
- Tests: use `pytest`; keep the tests to a minimum; use parametrized tests when possible; do not add useless comments; the tests shall be self-explanatory.
- Pytest fixtures: use them to avoid code duplication; use `conftest.py` for shared fixtures. Use `tmp_path` for file system operations.
- **Never suppress linter/type-checker warnings** by adding ignore rules to `pyproject.toml` or `# noqa` / `# type: ignore` comments. Always fix the underlying code instead.

## Definition of Done

Changes are NOT complete until:

- `pypeline run` executes with **zero failures**
- **All new functionality has tests** - never skip writing tests for new code
- Test coverage includes edge cases and error conditions
