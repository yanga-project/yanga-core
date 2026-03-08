# Architecture

yanga-core is designed as a build-system-agnostic SPL framework. It provides the domain model, pipeline orchestration, and reusable steps — without coupling to any specific build backend.

## Package Structure

```
yanga_core/
  domain/              # Core business logic and data models
    config.py          # YAML configuration dataclasses
    components.py      # Runtime component model
    execution_context.py  # Pipeline execution context
    spl_paths.py       # Build directory conventions
    artifact.py        # Inter-step artifact registry
    generated_file.py  # File generation utilities
    reports.py         # Report data types
    project_slurper.py # Project discovery and loading
    config_slurper.py  # YAML file discovery and parsing
    config_utils.py    # Config collection utilities
    component_analyzer.py  # Component artifact analysis
  steps/               # Built-in pipeline steps
    kconfig_gen.py     # Feature model processing
    west_install.py    # Git dependency management
    poks_install.py    # Cross-platform tool installation
    generate_report_config.py  # Report aggregation
  commands/            # CLI command implementations
    run.py             # Pipeline execution command
    base.py            # Command infrastructure
    report_config.py   # Component report filtering
    fix_html_links.py  # HTML link correction
    cppcheck_report.py # Static analysis report conversion
    filter_compile_commands.py  # Compilation database filtering
  docs/                # Documentation utilities
    sphinx.py          # Sphinx integration and configuration
  ini.py               # INI/TOML configuration loading
```

## Layered Design

```{mermaid}
graph TB
    subgraph "Build Backend (e.g., yanga)"
        CMakeGenerators[CMake Generators]
        CMakeSteps[CMake Steps]
        CMakeCommands[CMake Commands]
    end

    subgraph "yanga-core"
        Commands[Commands]
        Steps[Pipeline Steps]
        Domain[Domain Model]
        Docs[Sphinx Integration]
    end

    CMakeGenerators --> Domain
    CMakeSteps --> Domain
    CMakeCommands --> Commands
    Commands --> Domain
    Steps --> Domain
    Docs --> Domain
```

The build backend depends on yanga-core, never the reverse. yanga-core has no knowledge of CMake, Ninja, Make, or any other build system.

## Data Flow

```{mermaid}
sequenceDiagram
    participant User
    participant RunCommand
    participant ProjectSlurper
    participant ExecutionContext
    participant Steps
    participant DataRegistry

    User->>RunCommand: yanga run --variant X --platform Y
    RunCommand->>ProjectSlurper: discover & parse yanga.yaml files
    ProjectSlurper-->>RunCommand: variants, platforms, components
    RunCommand->>ExecutionContext: create with resolved config
    RunCommand->>Steps: execute pipeline steps in order

    loop For each step
        Steps->>ExecutionContext: read components, spl_paths
        Steps->>DataRegistry: read upstream data
        Steps->>Steps: execute step logic
        Steps->>DataRegistry: publish outputs (Artifacts, Reports)
    end
```

## Key Design Principles

### Build-system agnosticism
The domain model uses generic concepts (components, variants, platforms, artifacts) without referencing any build system. Build-system-specific code lives in separate packages that depend on yanga-core.

### Config-driven extensibility
Pipeline steps and generators are referenced by Python module path in YAML configuration. Users can add custom steps without modifying yanga-core.

### Typed inter-step communication
The `data_registry` provides a typed append-only bus. Steps publish and consume specific types (`Artifact`, `ReportRelevantFiles`, etc.), making dependencies between steps explicit and type-safe.

### Convention over configuration
`SPLPaths` encodes sensible directory layout defaults. Components, variants, and platforms follow naming conventions that minimize boilerplate configuration.

### Distributed configuration
Multiple `yanga.yaml` files are discovered and merged. Each directory can define its own components, keeping configuration close to the code it describes.
