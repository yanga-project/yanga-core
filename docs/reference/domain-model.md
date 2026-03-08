# Domain Model

yanga-core's domain model represents the key entities of a Software Product Line.

## Components

A `Component` is the basic building block of a product. It represents a self-contained unit with sources, include directories, tests, and documentation.

### ComponentConfig (YAML)

Defined in `yanga.yaml`:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Component name (required) |
| `description` | `str` | Human-readable description |
| `sources` | `list[str]` | Source file paths (relative to component location) |
| `include_directories` | `list[IncludeDirectory]` | Include paths with `PUBLIC`/`PRIVATE` scope |
| `required_components` | `list[str]` | Dependencies on other components |
| `testing` | `TestingConfiguration` | Test sources and mocking configuration |
| `docs` | `DocsConfiguration` | Documentation sources |
| `alias` | `str` | Alternative name for referencing this component |
| `path` | `str` | Override component root directory (relative to project root) |
| `components` | `list[str]` | Sub-components grouped under this component |

### Component (Runtime)

The runtime `Component` object resolves all paths and provides:

- `name`, `path` — resolved component identity and location
- `sources` — resolved source file paths
- `include_dirs` — resolved `IncludeDirectory` list
- `testing` — `TestingConfiguration` with resolved test sources
- `docs` — `DocsConfiguration` with resolved doc sources
- `is_subcomponent` — whether this component is nested under another

### Include Directories

```yaml
include_directories:
  - path: "include"
    scope: PUBLIC     # exposed to dependent components
  - path: "src"
    scope: PRIVATE    # only for this component's compilation
```

Transitive resolution: when component A requires component B, A inherits B's `PUBLIC` include directories. `IncludeDirectoriesResolver` handles this transitively and detects circular dependencies.

## Variants

A `VariantConfig` defines a product configuration:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Variant name (required) |
| `description` | `str` | Human-readable description |
| `components` | `list[str]` | Component names included in this variant |
| `features_selection_file` | `str` | KConfig feature selection file |
| `configs` | `list[ConfigFile]` | Variant-level config entries |
| `platforms` | `dict[str, VariantPlatformsConfig]` | Platform-specific overrides |

### Platform Overrides

Per-platform overrides add components and configs when building for a specific platform:

```yaml
variants:
  - name: MyProduct
    components: [main]
    platforms:
      arm_target:
        components: [hal_arm]
        configs:
          - id: west
            content: {...}
```

## Platforms

A `PlatformConfig` defines a target environment:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Platform name (required) |
| `description` | `str` | Human-readable description |
| `generators` | `list[GenericPipelineConfig]` | Build system generators for this platform |
| `build_types` | `list[str]` | Allowed build types (e.g., `Debug`, `Release`) |
| `build_targets` | `list[str]` | Available build targets |
| `configs` | `list[ConfigFile]` | Platform-level config entries |
| `components` | `list[str]` | Platform-specific components |

## SPLPaths

`SPLPaths` resolves all file system paths for a build context:

| Property | Value |
|----------|-------|
| `project_root_dir` | Project root |
| `build_dir` | `<project_root>/.yanga` or `<project_root>/build` |
| `variant_build_dir` | `<build_dir>/<variant>/<platform>/<build_type>` |
| `external_dependencies_dir` | `<build_dir>/external` |

Methods:
- `locate_artifact(name, search_paths)` — find a file by name across variant, project, and platform directories
- `get_component_build_dir(component_name)` — returns `<variant_build_dir>/<component_name>`

## Artifact

An `Artifact` represents a build output published to `data_registry` for inter-step communication:

```python
@dataclass
class Artifact:
    path: Path                           # file or directory
    provider: str                        # step that produced this
    consumers: list[str] | None = None   # None = global; list = restricted
    labels: list[str] | None = None      # semantic labels
```

Well-known labels:

| Label | Meaning |
|-------|---------|
| `include` | Path is an include directory |
| `public` | Re-export to dependent components |
| `private` | Visible only to declared consumers |
| `source` | Contains generated source files |

Filtering utilities:

- `with_label(label)` — predicate matching artifacts with a specific label
- `for_consumer(name)` — predicate matching artifacts available to a consumer
- `filter_artifacts(*predicates)` — compose predicates to filter artifact lists
- `collect_directories()` — extract unique directory paths from artifacts

## ExecutionContext

The central runtime object passed to all pipeline steps:

| Property | Type | Description |
|----------|------|-------------|
| `project_root_dir` | `Path` | Project root directory |
| `user_request` | `UserRequest` | What the user asked to build |
| `variant_name` | `str` | Selected variant |
| `platform` | `PlatformConfig` | Selected platform |
| `variant` | `VariantConfig` | Selected variant config |
| `components` | `list[Component]` | Resolved components for this variant+platform |
| `spl_paths` | `SPLPaths` | Path resolver |
| `data_registry` | inherited | Inter-step data bus |

### UserRequest

```python
@dataclass(frozen=True)
class UserRequest:
    scope: UserRequestScope      # VARIANT or COMPONENT
    variant_name: str
    component_name: str | None
    target: UserRequestTarget | str
    build_type: str | None
```

`UserRequestTarget` values: `NONE`, `ALL`, `BUILD`, `COMPILE`, `CLEAN`, `TEST`, `COVERAGE`, `MOCKUP`, `LINT`, `DOCS`, `REPORT`, `RESULTS`.

## GeneratedFile

Utilities for writing generated files:

- `GeneratedFileIf` (abstract) — defines `path`, `to_string()`, `to_file()`
- `GeneratedFile` — concrete implementation wrapping a string content

## Reports

Report data types for documentation pipelines:

- `ReportRelevantFiles` — files contributed by steps/generators for report inclusion
- `FeaturesReportRelevantFile` — KConfig features JSON file reference
- `ComponentReportData` — aggregated report data for a single component
- `VariantReportData` — aggregated report data for a variant
- `ReportData` — complete report configuration written as `report_config.json`

`ReportRelevantFileType` categories: `DOCS`, `SOURCES`, `TEST_RESULT`, `LINT_RESULT`, `COVERAGE_RESULT`, `OTHER`, `HTML`.
