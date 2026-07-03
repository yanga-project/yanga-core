# Built-in Pipeline Steps

yanga-core ships with pipeline steps for feature model handling, dependency acquisition, and report generation.

## `KConfigGen`

**Module:** `yanga_core.steps.kconfig_gen`

Processes KConfig feature models to generate C headers, JSON configuration, and Markdown documentation.

**Outputs** (in `<variant_build_dir>/kconfig/`):

| File | Description |
|------|-------------|
| `autoconf.h` | C header with `#define` macros for all selected features |
| `autoconf.json` | JSON representation of the full configuration data |
| `autoconf.md` | Markdown documentation with feature summary table |

**Side effects:**
- Registers an `Artifact` with labels `["include", "public"]` so all components can `#include "autoconf.h"`
- Registers a `FeaturesReportRelevantFile` and `ReportRelevantFiles` entry for the documentation pipeline

**Inputs:** User config files and KConfig source files.

**Configuration:** The variant must declare a `features_selection_file` pointing to a KConfig selection file.

---

## `WestInstall`

**Module:** `yanga_core.steps.west_install`

Manages external Git repository dependencies using [Zephyr West](https://docs.zephyrproject.org/latest/develop/west/index.html).

**Behavior:**
- Collects West manifests from `data_registry` and from configs with `id: west`
- Resolves workspace directory in priority order: `data_registry` value, config value, or `spl_paths.external_dependencies_dir`
- Clones/updates repositories according to the merged manifest

**Configuration:** Declare dependencies using `configs` with `id: west` in variants or platforms.

---

## `PoksInstall`

**Module:** `yanga_core.steps.poks_install`

Installs cross-platform tool dependencies using [Poks](https://github.com/cuinixam/poks). Works on Windows, Linux, and macOS.

**Behavior:**
- Collects and merges configs with `id: poks`
- Installs tools into `~/.poks/`
- Makes installed tool paths and environment variables available to subsequent steps

**Configuration:** Declare dependencies using `configs` with `id: poks` in variants or platforms.

---

## `GenerateReportConfig`

**Module:** `yanga_core.steps.generate_report_config`

Aggregates all `ReportRelevantFiles` and `FeaturesReportRelevantFile` entries from `data_registry` into a single `report_config.json` file.

**Output:** `<variant_build_dir>/report_config.json`

**Behavior:**
- Groups report-relevant files by component (using `UserRequest.component_name`)
- Creates `ComponentReportData` for each component and `VariantReportData` for variant-scoped files
- Serializes the complete `ReportData` as JSON

This step should be placed after all steps and generators that register report-relevant files, and before any step that consumes the report configuration (e.g., a build step that invokes Sphinx).

---

## `RegisterSplPaths`

**Module:** `yanga_core.steps.register_spl_paths`

First step of the SPL report pipeline (see [Generate an SPL report](../how-to/spl-report.md)): reads the project settings (`yanga.ini` / `pyproject.toml`) once and registers a project-scope `SPLPaths` in the data registry. The other SPL report steps resolve every path through the registered `SPLPaths` — including the report output directory (`.yanga/build/spl/reports`, or `build/spl/reports` when `create_yanga_build_dir` is disabled) — and take no path configuration of their own.

---

## `CollectVariantReports`

**Module:** `yanga_core.steps.collect_variant_reports`

Discovers every built variant report on disk and gathers it into `<spl_report_dir>/variants/…`, registering a `CollectedVariantReport` for each one. The collected layout (mirroring the build tree) plus the registrations are the hand-off contract for the following steps: every source deposits into the same structure, so downstream never cares whether a report was built locally or downloaded.

**Behavior (`local` source):**
- Discovery is marker-based: a variant build leaves its `report_config.json` next to the rendered `reports/` directory, so this step globs the variant build root for variant-scope markers with a rendered `reports/index.html` — whatever the build layout depth (with or without a build type). No project configuration is consulted: whatever was built is collected, including builds of since-removed variants until their build directories are wiped.
- Copies each discovered `reports/` directory into the collected layout, preserving its path relative to the variant build root (e.g. `variants/Disco/gtest/Debug/`)

**Configuration:**

| Option | Default | Description |
|--------|---------|-------------|
| `source` | `local` | Where the built reports come from (`local` only for now) |

---

## `GenerateSplReportConfig`

**Module:** `yanga_core.steps.generate_spl_report_config`

The SPL analogue of `GenerateReportConfig`: turns the registered `CollectedVariantReport` entries into a `report_config.json` with `scope: SPL`, containing one HTML link per collected variant report.

**Output:** `<spl_report_dir>/report_config.json`

**Configuration:**

| Option | Default | Description |
|--------|---------|-------------|
| `project_name` | project directory name | Product-line display name used as the report title |

---

## `SphinxBuildReport`

**Module:** `yanga_core.steps.sphinx_build_report`

Runs `sphinx-build` over the project's `conf.py`/`index.md` with the `REPORT_CONFIGURATION_FILE` environment variable pointing at the generated SPL report config, writing the site to `<spl_report_dir>`. Afterwards it fixes the external artifact links (the `#http://` marker links), which also makes them open in a new tab — an external report is a separate site with its own navigation, so opening it in place would trap the reader.

**Configuration:**

| Option | Default | Description |
|--------|---------|-------------|
| `source_dir` | `.` | Sphinx source directory (holds `conf.py` and the master `index.md`) |
