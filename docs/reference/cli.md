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
| `--variant-name <NAME>` | Product variant to build |
| `--component <NAME>` | Narrow scope to a single component |
| `--target <NAME>` | Specific build target |
| `--build-type <TYPE>` | Build type (e.g., `Debug`, `Release`) |
| `--step <NAME>` | Run pipeline up to this step |
| `--single` | Run only the specified step (with `--step`) |
| `--force-run` | Force step re-execution regardless of change detection |
| `--print` | Print project configuration without executing |
| `--not-interactive` | Fail instead of prompting for user input |

If `--variant-name` or `--platform` are not provided and multiple options exist, the user is prompted interactively (unless `--not-interactive` is set).

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
