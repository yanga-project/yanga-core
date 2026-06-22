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

## Lazy Component Resolution

A component's paths (its root, its sources, its include directories) are resolved at
**consumption time** during build-system generation, not at config-load (slurp) time.
The component set a generator sees is the **declared** components plus any
**registered** by an earlier step at run time.

### Why not resolve at slurp

The slurper runs once, before the pipeline, while the `ExecutionContext` is built. If
it resolves and validates the whole component graph there, two real cases become
impossible:

- **External components.** A component whose root lives inside a fetched dependency
  has no resolvable path until the install step runs, because that path is only
  published (as an `ExternalProject` on the data registry) by `WestInstall` during the
  install phase, which is after the slurp. Resolving it earlier is a chicken-and-egg:
  the install step needs the context the slurp produces. The eager slurp is also why
  such components have to hardcode `.yanga/ext/...`, which bakes in both the workspace
  layout and the install layout and breaks the moment either changes.
- **Generated components.** A code generator may emit a component (a generated RTE,
  per-feature components) that did not exist when the slurper read the files.

Include resolution makes this worse, not better. Because include directories are
derived from `component.path` and inherited transitively through `required_components`,
a single late-bound component poisons the eager walk for itself and for every
component that depends on it. So lazy resolution is the prerequisite; external and
generated components ride on it. (The previous split, sources resolved lazily but
include directories resolved eagerly at slurp, was the inconsistency that pointed
here.)

### The shape

- **Two types.** The declared `Component` produced by the slurper holds only the
  declaration: a root spec (in-tree path, or `external: <project>` plus a path
  relative to the resolved project), sources/test/docs as strings,
  private/public include directories unresolved, and `required_components` as written.
  It is immutable with respect to resolution. A separate `ResolvedComponent`, produced
  by the resolver, carries the absolute root, the located source files, and the
  resolved include-directory list. Resolution is a pure function of the declared set
  plus the execution context, so it can be re-run (per variant/platform, or after a
  late registration) without mutating any half-resolved object.
- **A dedicated `ComponentResolver`,** not an extension of `ComponentAnalyzer`. The
  transitive include walk needs the *full* component set and the resolver needs the
  data registry (for external roots and registered components), neither of which the
  per-subset, `SPLPaths`-only `ComponentAnalyzer` has. Keeping resolution in one place
  leaves `ComponentAnalyzer` a thin analysis helper over already-resolved components.
- **Component set = declared + registered.** A step may publish a `Component` to the
  data registry, the same way `WestInstall` publishes an `ExternalProject`; the
  resolver reads the union. Generated components are declared-shaped records
  contributed late.

### The resolver

To resolve one component you need all of them: a component's resolved include path is
its own private includes plus the transitively inherited public includes of everything
in its `required_components` closure. So `ComponentResolver` is a stateful object built
once per build with the **full** set (declared plus registered), indexed by name and
alias, not a free function over a single component.

`resolve(name)` resolves the component's root (in-tree under the project, or
`ExternalProject.path` from the registry for an external one), locates its sources
against that root, and computes its include directories via the transitive
`required_components` walk. It fails fast on an unknown component, a missing external
project, or a dependency cycle.

Two memo layers, both keyed by name, keep it from re-doing work: a resolved-component
cache so each component is resolved once no matter how many generators ask, and a
public-include cache so a diamond in the dependency graph walks each node once. The
memoization is sound because resolution is a pure function of the set and the context,
and the set is frozen for the resolver's lifetime. The resolver is created per build
(one variant, platform, context), and the lifecycle contract closes component
registration before the build phase, so the set never changes between `resolve` calls;
a new context yields a fresh resolver and a fresh cache. This in-memory memo is distinct
from the incremental-build cache, which is `get_inputs()` folding in the resolved
external roots and registered-component identity.

This is the existing `IncludeDirectoriesResolver` generalized: it already owns the full
set, walks `required_components` transitively, detects cycles, and caches per node. The
change is to run it at consumption instead of slurp, extend root resolution to the
registry (external) case, add source location, and emit an immutable `ResolvedComponent`
rather than mutating `Component.include_dirs`.

### Consequences

- **Validation moves with resolution.** The slurp keeps only cheap local checks
  (duplicate name/alias). Required-component existence, cycle detection, missing
  external project, and missing source files move to the resolve pass, so they tolerate
  members produced earlier in the same run.
- **Cache correctness.** A resolved external root carries the dependency's revision and
  a registered component is a run-time input, so the generation step's `get_inputs()`
  must fold both in, or an incremental build serves a stale tree.
- **Lifecycle contract.** External roots require the install phase to have run before
  any resolve call; generated components must be registered no later than the
  generation phase, which the build phase then treats as final. The existing
  install → gen → build ordering already satisfies this.
- **Backward compatibility.** In-tree components with a relative path resolve exactly
  as before, only later. The one observable change is that graph errors surface during
  generation instead of at load.

This is staged: (A) move path and include resolution off the slurp into the resolver,
behaviour-preserving except error timing; (B) add the `external:` root spec; (C) allow
components to be registered at run time. This decision records the end state; each
stage lands behind its own plan.
