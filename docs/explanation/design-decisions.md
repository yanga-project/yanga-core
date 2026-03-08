# Design Decisions

Key architectural decisions that shaped yanga-core.

## Two-Package Split

yanga-core was extracted from the monolithic `yanga` package to separate build-system-agnostic SPL framework code from CMake-specific implementation. The result is a clean two-package architecture:

| Package | Contents |
|---------|----------|
| **yanga-core** | Domain model, pipeline orchestration, built-in steps, CLI commands |
| **yanga** | CMake generators, CMake build steps, CMake-specific commands |

This separation allows other build backends (Ninja, Make, Bazel, etc.) to build on yanga-core without inheriting CMake dependencies.

## Default Steps Ship with yanga-core

Built-in pipeline steps (`KConfigGen`, `WestInstall`, `PoksInstall`, `GenerateReportConfig`) are part of yanga-core rather than a separate package. The rationale:

- **Feature models** (`KConfigGen`) are a foundational SPL concept — users expect feature model support out of the box
- **Dependency acquisition** (`WestInstall`, `PoksInstall`) is a build prerequisite, not an optional plugin
- **Report configuration** (`GenerateReportConfig`) operates purely on domain types with no build-system dependency
- These steps are stable and tightly bound to `ExecutionContext`, which lives in yanga-core

A separate `yanga-steps` package was considered and rejected — it would add distribution complexity without meaningful benefit.

## Feature Models as First-Class

Feature models are handled through `KConfigGen` rather than as a generic `ConfigFile` with type `"kconfig"`. While the `ConfigFile` mechanism works well for tool configuration (west manifests, toolchain files), feature models deserve special treatment because:

- They determine the **variant space** — the set of valid product configurations
- They produce **build-wide artifacts** (`autoconf.h`) consumed by every component
- They generate **feature documentation** as part of the SPL's engineering output
- The `kspl` library provides rich domain types beyond simple file-path resolution

## Artifact as Generic Inter-Step Contract

The `Artifact` dataclass replaced build-system-specific mechanisms (like `IncludeDirectoriesProvider`) for communicating step outputs. Benefits:

- **Labels** (`include`, `public`, `source`) provide semantic meaning without coupling to a specific build system
- **Consumer scoping** (`consumers` field) supports both global artifacts and component-specific ones
- **Uniform querying** via `filter_artifacts()`, `with_label()`, `for_consumer()`

## SPLPaths Convention

The directory layout convention (`<build_dir>/<variant>/<platform>/<build_type>/`) is owned by yanga-core's `SPLPaths`, not by build backends. This ensures that any code needing component build paths (e.g., `GenerateReportConfig`) can resolve them without importing build-system-specific code.

## ConfigFile Mechanism

The `configs` mechanism with well-known `id` strings decouples components from step implementations:

- A component declares `id: "autosar"` — it doesn't know which step handles it
- A step declares it handles `id: "autosar"` — it doesn't know which components use it
- Discovery happens at runtime via `collect_configs_by_id()`

This is the same pattern used for `west`, `poks`, and `toolchain` configurations.
