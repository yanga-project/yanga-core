# Command Line Interface

yanga-core provides CLI commands for pipeline execution and report utilities.

## `yanga run`

Executes the build pipeline for a selected variant and platform.

```bash
yanga run [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--platform <NAME>` | Target platform |
| `--variant <NAME>` | Product variant to build |
| `--component <NAME>` | Narrow scope to a single component |
| `--target <NAME>` | Specific build target |
| `--build-type <TYPE>` | Build type (e.g., `Debug`, `Release`) |
| `--step <NAME>` | Run pipeline up to this step |
| `--single` | Run only the specified step (with `--step`) |
| `--force-run` | Force step re-execution regardless of change detection |
| `--print` | Print project configuration without executing |
| `--not-interactive` | Fail instead of prompting for user input |

If `--variant` or `--platform` are not provided and multiple options exist, the user is prompted interactively (unless `--not-interactive` is set).

## `yanga features`

Shows the product features of all variants, or edits one selection, by running the `pipeline:` of a `feature_model:` block.

```bash
yanga features [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--variant <NAME>` | Variant whose selection to edit |
| `--platform <NAME>` | Platform whose feature model to open; needs `--variant` |
| `--gui` / `--no-gui` | GUI editor (default) or terminal editor |

The flags pick the model and what happens:

| Flags | Model | Result |
|-------|-------|--------|
| none | the project's `feature_model:` | kspl's viewer with every variant's product selection (GUI only) |
| `--variant` | the project's `feature_model:` | editor on the variant's selection |
| `--variant` and `--platform` | that platform's `feature_model:` | editor on the variant's selection for that platform |

A platform that declares no `feature_model:` block is an error when passed as `--platform`; the product model is never opened for a platform. `--platform` on its own is an error too: a platform model is opened by the platform's own tool, which configures a build of a variant. The request reaches the steps as `UserRequest(target=FEATURES, variant_name, platform_name, extra={"gui": ...})`.

## `yanga report_config`

Creates a component-specific report configuration by filtering a variant-level `report_config.json` to a single component.

**Arguments:**
- `--component-name` — component to filter for
- `--variant-report-config` — path to the variant-level `report_config.json`
- `--output-file` — path for the filtered output

## `yanga fix_html_links`

Fixes incorrect Sphinx-generated HTML links where `href="./path/file.html#http://"` patterns appear. Processes all HTML files under the given directory using parallel threads.

**Arguments:**
- `--report-dir` — root directory of the HTML report
- `--verbose` — enable detailed logging

## `yanga cppcheck_report`

Converts CppCheck XML output to a Markdown report. Groups errors by file and severity, and includes source code context.

**Arguments:**
- `--input-file` — CppCheck XML file
- `--output-file` — output Markdown file
- `--project-dir` — (optional) project root for relative path display

## `yanga filter_compile_commands`

Filters a `compile_commands.json` compilation database to include only entries for specified source files. Uses `clanguru` for parsing.

**Arguments:**
- `--compilation-database` — path to `compile_commands.json`
- `--source-files` — list of source file paths to keep
- `--output-file` — path for the filtered output

## `python -m yanga_core.commands kconfig_view`

Not a user command: `python -m yanga_core.commands` only carries helpers a pipeline step runs as its own process, while `run`, `info` and `features` are classes the `yanga` CLI calls directly. Shows the product feature model with every variant's declared `feature_selection` in kspl's viewer. The [`KConfigEdit`](steps.md#kconfigedit) step runs it as its own process with the pipeline's environment when neither a variant nor a platform is selected; it waits until the window is closed.

**Arguments:**
- `--project-dir` — project root directory; the model is the project's `feature_model:` block
