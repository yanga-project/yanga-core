# Configuration

yanga-core discovers and parses all `yanga.yaml` files in a project. Some directories are excluded automatically (`.git`, `.github`, `.vscode`, `build`, `.venv`) to avoid unnecessary parsing.

## Configuration File Name

The default configuration file name is `yanga.yaml`. Override it with a `yanga.ini` file or a `pyproject.toml` entry.

### INI File

```ini
[default]
configuration_file_name = build.yaml
exclude_dirs = .git, build, .venv
```

### TOML File

```toml
[tool.yanga]
configuration_file_name = "build.yaml"
exclude_dirs = [".git", "build", ".venv"]
```

## YAML Schema

A `yanga.yaml` file can contain any combination of the following top-level keys:

```yaml
pipeline:       # Pipeline stage and step definitions
feature_model:  # The product feature model
variants:       # Product variant definitions
platforms:      # Platform/target definitions
components:     # Component definitions
configs:        # Project-level configuration entries
```

Multiple `yanga.yaml` files are merged. Components, variants, and platforms are collected from all files. This allows a distributed project layout where each directory defines its own components. Only one file may declare `pipeline:`, and only one may declare `feature_model:`.

## Feature Models and Selections

A feature model is a KConfig root file. A selection is a file of symbol values for one model. The project declares the product model; a platform whose configuration lives elsewhere (Zephyr's Kconfig, for example) declares its own. The two models never mix: a selection file belongs to exactly one of them.

```yaml
feature_model:                    # product model
  description: Product features
  file: KConfig                   # next to this file, else in the project root

platforms:
  - name: zephyr
    feature_model:                # platform model, replaces the product one for --platform
      file: zephyr/Kconfig
    feature_selection:            # the platform's defaults
      file: platforms/zephyr/prj.conf

variants:
  - name: Disco
    feature_selection:            # product selection, used by KConfigGen
      file: config.txt
    platforms:
      zephyr:
        feature_selection:        # this variant's selection for the zephyr model, on top of the defaults
          file: variants/Disco/zephyr.conf
```

Each step reads the model and the selection files it serves. `KConfigGen` serves the product: the top-level `feature_model` and the variant's `feature_selection`. A step serving a platform model reads the platform's `feature_model`, the platform's `feature_selection` as the defaults and the variant's entry for that platform on top. A model may also declare a `pipeline:`, the steps that prepare it for editing; no command runs it yet.

## `configs` Entries

The `configs` mechanism provides a generic way to pass typed configuration to pipeline steps. Each entry has an `id` and either `file` or `content`:

```yaml
configs:
  - id: west
    content:
      remotes: [...]
      projects: [...]
  - id: toolchain
    file: "path/to/toolchain.cmake"
```

Well-known config IDs used by built-in steps:

| ID | Consumer Step | Purpose |
|----|---------------|---------|
| `west` | `WestInstall` | Git repository dependencies |
| `poks` | `PoksInstall` | Cross-platform tool dependencies |
| `toolchain` | Build backend | Toolchain file path |
| `vars` | Build backend | Custom key-value build variables |

Configs can appear at project, variant, platform, or variant-platform level. Steps collect them via `collect_configs_by_id()` in priority order: project, variant, platform, variant-platform.

## `YangaIni` Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `configuration_file_name` | `str` | `"yanga.yaml"` | Name of configuration files to discover |
| `exclude_dirs` | `list[str]` | `[]` | Additional directories to skip during discovery |
| `create_yanga_build_dir` | `bool` | `True` | Whether to create a `.yanga` build directory |

Settings are loaded from `yanga.ini` and/or `pyproject.toml` (TOML takes precedence).
