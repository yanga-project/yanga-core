# API Reference

Key classes and functions in the yanga-core Python API.

## Project Discovery

### `YangaProjectSlurper`

**Module:** `yanga_core.domain.project_slurper`

Main entry point for loading a project's configuration.

```python
slurper = YangaProjectSlurper(
    project_dir=Path("."),
    configuration_file_name="yanga.yaml",
    exclude_dirs=[],
    create_yanga_build_dir=True,
)
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `user_config_files` | `list[Path]` | Paths to all discovered `yanga.yaml` files |
| `project_configs` | `list[ConfigFile]` | Top-level config entries |
| `components_configs_pool` | `ComponentsConfigsPool` | All component definitions indexed by name |
| `pipeline` | `list` | Pipeline stage definitions |
| `variants` | `list[VariantConfig]` | All variant definitions |
| `platforms` | `list[PlatformConfig]` | All platform definitions |

**Methods:**

- `get_variant_config(name)` — retrieve a `VariantConfig` by name
- `get_variant_components(variant_name, platform_name)` — resolve components for a variant+platform, including platform-specific additions
- `get_platform(platform_name)` — retrieve a `PlatformConfig` by name
- `print_project_info()` — log project structure for debugging

### `YangaConfigSlurper`

**Module:** `yanga_core.domain.config_slurper`

Lower-level utility for finding and parsing `yanga.yaml` files.

```python
slurper = YangaConfigSlurper(project_dir, exclude_dirs, configuration_file_name)
configs: list[YangaUserConfig] = slurper.slurp()
```

## Configuration Utilities

### `collect_configs_by_id`

**Module:** `yanga_core.domain.config_utils`

Collect all `ConfigFile` entries with a given `id` from the execution context, merged in priority order:

```python
from yanga_core.domain.config_utils import collect_configs_by_id

configs = collect_configs_by_id(execution_context, "west")
# Returns list[ConfigFile] from project → variant → platform → variant-platform
```

### `parse_config`

**Module:** `yanga_core.domain.config_utils`

Parse a `ConfigFile` into a typed dataclass:

```python
from yanga_core.domain.config_utils import parse_config

manifest = parse_config(config_file, WestManifest, base_path=project_dir)
```

## Component Analysis

### `ComponentAnalyzer`

**Module:** `yanga_core.domain.component_analyzer`

Analyze component artifacts for build system generation:

```python
analyzer = ComponentAnalyzer(components, spl_paths)
sources = analyzer.collect_sources()
test_sources = analyzer.collect_test_sources()
include_dirs = analyzer.collect_include_directories()
testable = analyzer.get_testable_components()
```

### `IncludeDirectoriesResolver`

**Module:** `yanga_core.domain.project_slurper`

Resolves transitive include directory dependencies across components. Detects circular dependencies.

```python
resolver = IncludeDirectoriesResolver()
resolved_components = resolver.populate(components)
```

## Artifact Registry

### Filtering Functions

**Module:** `yanga_core.domain.artifact`

```python
from yanga_core.domain.artifact import (
    Artifact,
    with_label,
    for_consumer,
    filter_artifacts,
    collect_directories,
)

# Get all include artifacts for a specific component
artifacts = execution_context.data_registry.get(Artifact)
includes = filter_artifacts(
    with_label("include"),
    for_consumer("my_component"),
)(artifacts)
dirs = collect_directories()(includes)
```

## Sphinx Integration

### `SphinxConfig`

**Module:** `yanga_core.docs.sphinx`

Environment-based Sphinx configuration reader. Reads the `REPORT_CONFIGURATION_FILE` environment variable to load report data.

```python
sphinx_config = SphinxConfig()
report = sphinx_config.report_data       # SphinxReportConfig or None
patterns = sphinx_config.include_patterns  # list of file paths for Sphinx
```

### `SphinxReportConfig`

**Module:** `yanga_core.docs.sphinx`

Extends `ReportData` with Sphinx-specific utilities:

- `from_json_file(path)` — load and parse `report_config.json`
- `create_component_myst_toc(component_name)` — generate a MyST toctree directive for a component's documentation files
- `get_component_files_list()` / `get_variant_files_list()` — collect relativized file paths
