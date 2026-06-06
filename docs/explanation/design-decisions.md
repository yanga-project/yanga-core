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

## Configuration Provenance

Every config element parsed from a `yanga.yaml` carries a `location` (file, line, column). This serves two user-facing needs:

- **Correct cache invalidation.** Scoped dependency fragments (`scoop`, `poks`, `west`) can be declared in any `yanga.yaml` — root, variant, platform, or variant-platform. A step's `get_inputs()` reads each collected fragment's `location.file`, so editing a dependency in *any* of those files re-runs the step instead of serving a stale toolchain.
- **Pinpointed errors.** A malformed value reports `file:line:column` (e.g. `platform.yaml:3:5: Field "level" ...`), so the user finds their typo without searching the tree.

How it is filled, end to end:

1. A position-preserving YAML loader stamps each mapping with its position as a Python **attribute** on the dict, never a key. Using an attribute keeps free-form passthrough payloads (a `content:` blob forwarded verbatim to another parser) byte-clean.
2. `ConfigElement` is the base for every locatable element. In `__pre_deserialize__` it lifts that attribute into a `location` key so mashumaro fills the field itself — doing all the nested/list/alias matching natively, no hand-written tree walk to drift out of sync.
3. The `location` field is `kw_only` (so subclasses keep mandatory positional fields), `compare=False` (so equal elements from different files still dedup when fragments merge), and stripped on export (so serialized config never carries provenance).

Error localization uses a small per-parse **stack** of locations (a `ContextVar` for thread-safety under the parallel slurp), used only for messages — it never touches the `location` data. Each element pushes on entry and pops on successful construction, so the stack top is always the element currently being built. A single "deepest element seen" slot is *not* enough: when a parent's scalar field fails after a nested child already parsed, the slot still points at the innocent child, whereas the stack has popped the child and correctly names the parent.

`location` is reserved, and the name could collide in two independent ways — both are guarded, not just documented:

- **A user writes `location:` as a yaml key.** The field's wire key is aliased to `_yanga_location`, so the loader injects provenance under that internal key and a user's `location:` becomes an ignored unknown key rather than being routed into the provenance field. (The Python field is still named `location`, so `obj.location` is unchanged.)
- **A developer declares a `location:` field on a `ConfigElement` subclass.** An `__init_subclass__` check raises `TypeError` at definition time, so the shadowing surfaces immediately for whoever edits the config schema — a comment on the base field would never be seen there.
