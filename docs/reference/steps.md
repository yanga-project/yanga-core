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
