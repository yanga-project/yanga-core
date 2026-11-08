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

**Configuration:** The variant declares a `feature_selection:` block pointing to a KConfig selection file.

| Key | Default | Description |
|-----|---------|-------------|
| `kconfig_model_file` | `KConfig` | KConfig model file, relative to the project root |
| `output_stem` | `autoconf` | Base name of the three generated files, e.g. `product_features` gives `product_features.h` |

---

## `KConfigEdit`

**Module:** `yanga_core.steps.kconfig_edit`

Opens kconfiglib's editor on the requested feature model and saves into the declared selection file. It is the last step of a `feature_model:` pipeline, the project's or a platform's, run by `yanga features`. A model whose editor is a tool of its own, such as Zephyr's `menuconfig` build target, declares that tool in its pipeline instead of this step.

**Behavior:** the request's variant and platform decide the model and the one selection file.

| Request | Model | Selection file |
|---------|-------|----------------|
| neither | project `feature_model.file` | none opened for editing; runs [`kconfig_view`](cli.md), every variant's selection side by side in kspl's viewer |
| variant | project `feature_model.file` | variant `feature_selection.file` |
| variant and platform | platform `feature_model.file` | variant `platforms.<platform>.feature_selection.file` |

- Selection files are looked up next to the file that declares them, then in the project
- Runs kconfiglib's own editor as its own process in the terminal, `python -m guiconfig <model>`, with the selection file in `KCONFIG_CONFIG` and the pipeline's environment, in the model's directory. That is the editor's documented command line, so the editor loads and saves that one file
- Reads `gui` from `UserRequest.extra`: `true` (default) opens `guiconfig`, `false` opens `menuconfig`; the viewer has no terminal form
- Has no inputs and no outputs, so it always runs

**Errors:** a missing `feature_model:` block, no variant, or an undeclared output file: the variant's selection, or the variant's platform selection for a variant and platform request. The editor never saves into an undeclared file. A platform's own `feature_selection:` is a build input; this step never loads or writes it.

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

## `GenerateSplReportConfig`

**Module:** `yanga_core.steps.generate_spl_report_config`

The SPL analogue of `GenerateReportConfig`: writes a `report_config.json` with `scope: SPL` for the SPL documentation report. The project's `index.md` branches on that scope to document what belongs to the whole product line. The variants are listed by the SPL overview (`RenderSplOverview`), not here.

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

It registers the rendered report as a `PublishedFile`, so a `WritePublishManifest` after it lists the SPL documentation report in the SPL manifest.

---

## `WritePublishManifest`

**Module:** `yanga_core.steps.write_publish_manifest`

Writes `publish_manifest.json`: what this run publishes and where readers find it. The SPL overview reads only these manifests. Steps that make a file to publish register a `PublishedFile` (kind `REPORT` or `ARTIFACT`, a name and the path on disk); this step lists those whose file exists, so put it last.

- In a variant build it writes into `<variant_build_dir>` with the variant, platform, build type, the variant description and the selected features.
- In the SPL pipeline (after `RegisterSplPaths`) it writes into `<spl_build_dir>`.
- Both record the commit (`git rev-parse HEAD`, empty outside a git checkout) and the build time.
- Locally nothing is published, so each link is relative to the build dir, which is the site root. A file outside the build dir is an error: a `file://` link would break as soon as the site moves.

---

## `CollectPublishManifests`

**Module:** `yanga_core.steps.collect_publish_manifests`

Finds every `publish_manifest.json` under the variant build root and in the SPL build dir and registers it for `RenderSplOverview`. It reads only the disk and copies nothing: a download step that runs before it restores manifests and outputs into the same layout. Whatever was built is listed, including builds of removed variants until their build directories are wiped.

---

## `RenderSplOverview`

**Module:** `yanga_core.steps.render_spl_overview`

Renders the project's Jinja2 template to `<build_dir>/index.html`, the SPL overview. The template gets one object, `overview`, with:

- `project_name`, `generated_at`, `commit` (of the SPL documentation run)
- `documentation`: the entries of the SPL manifest (`kind`, `name`, `link`)
- `variants`: per variant `name`, `description`, `features` (from its newest build) and `builds`; per build `platform`, `build_type`, `commit`, `build_time`, `reports` and `artifacts`

Links are relative to the site root, so the template uses them as they are.

**Configuration:**

| Option | Default | Description |
|--------|---------|-------------|
| `project_name` | project directory name | Product-line display name |
| `template` | `spl_overview.html.jinja` | Template file, relative to the project root |
