# Concepts and Terminology

## Software Product Line

A **Software Product Line (SPL)** is a set of software-intensive systems that share a common, managed set of features satisfying the specific needs of a particular market segment. yanga-core provides the framework for managing SPL development.

## Domain Terms

Product
: A product from a company's product family. In yanga-core, a product is realized through one or more variants.

Variant
: A specific configuration of a product. Each variant selects a set of components and optionally a feature selection to produce a distinct product. Variants can have platform-specific overrides.

Component
: The basic building block of a product variant. A component is a self-contained unit with its own sources, include directories, dependencies, tests, and documentation. Components declare dependencies on other components via `required_components`.

Platform
: The target environment for which the product is built and deployed. Platforms define build system generators, toolchains, allowed build types, and platform-specific dependencies.

Pipeline
: The ordered sequence of steps that transforms source code and configuration into build outputs. Each stage groups related steps (e.g., `install`, `gen`, `build`).

Pipeline Step
: A single unit of work in the pipeline. Steps receive an `ExecutionContext` and can read/write to a shared `data_registry` for inter-step communication.

## Key Mechanisms

### Config Files

The `configs` mechanism is the generic way to pass typed configuration to pipeline steps. Each config entry carries an `id` string that steps use to discover relevant configuration. This decouples components and variants from specific step implementations — a component only declares _what_ it needs (e.g., `id: "autosar"`), not _which step_ provides it.

### Data Registry

The `data_registry` is a typed append-only bus on `ExecutionContext`. Steps publish data (e.g., `Artifact`, `ReportRelevantFiles`) and downstream steps or generators retrieve it by type. This is the primary mechanism for inter-step communication without introducing direct dependencies between steps.

### Artifact

An `Artifact` represents a step-produced output that other steps or the build system need to discover. It carries a `path`, a `provider` identifier, optional `consumers` (for scoping), and semantic `labels` (e.g., `include`, `public`, `source`).

### SPLPaths

`SPLPaths` encodes the directory layout convention for builds:

```
<project_root>/
  .yanga/                          # build_dir (or build/)
    <variant>/
      <platform>/
        <build_type>/              # variant_build_dir
          <component_name>/        # component_build_dir
          kconfig/                 # KConfigGen output
          report_config.json       # GenerateReportConfig output
    external/                      # external_dependencies_dir
```

This convention is build-system-agnostic. Build backends (e.g., CMake) may add their own overlays on top of these paths.

### Feature Models

Feature models are a foundational SPL concept. yanga-core treats them as first-class through the `KConfigGen` step, which processes KConfig definitions to produce C headers (`autoconf.h`), JSON configuration, and Markdown documentation. Feature selection files per variant determine which features are active.
