# Pipeline

yanga-core orchestrates builds through a configurable pipeline — a sequence of stages, each containing one or more steps.

## Pipeline Configuration

Define the pipeline in `yanga.yaml` as a list of named stages:

```yaml
pipeline:
  - install:
    - step: WestInstall
      module: yanga_core.steps.west_install
    - step: PoksInstall
      module: yanga_core.steps.poks_install
  - gen:
    - step: KConfigGen
      module: yanga_core.steps.kconfig_gen
  - build:
    - step: GenerateBuildSystemFiles
      module: yanga.steps.execute_build
    - step: GenerateReportConfig
      module: yanga_core.steps.generate_report_config
    - step: ExecuteBuild
      module: yanga.steps.execute_build
```

Each step is defined by:
- `step` — the Python class name
- `module` — the Python module where the class is located

## Execution Flow

1. `RunCommand` creates a `YangaProjectSlurper` to discover and parse all `yanga.yaml` files
2. The user selects (or provides) a variant, platform, and build type
3. An `ExecutionContext` is created with the resolved components and configuration
4. `PipelineStepsExecutor` runs each step in order, passing the `ExecutionContext`

## Smart Scheduling

The scheduler compares each step's `get_inputs()` and `get_outputs()` to decide whether re-execution is needed:

- If any input file is newer than the oldest output, the step runs
- If any output is missing, the step runs
- `--force-run` bypasses this check

## Data Registry

Steps communicate through `ExecutionContext.data_registry`, a typed append-only bus:

```python
# Producer step publishes data
self.execution_context.data_registry.append(my_artifact)

# Consumer step retrieves data
items = self.execution_context.data_registry.get(MyType)
```

Common types published to `data_registry`:

| Type | Publisher | Purpose |
|------|----------|---------|
| `Artifact` | `KConfigGen` | Include directory for generated headers |
| `ReportRelevantFiles` | Various steps | Files to include in reports |
| `FeaturesReportRelevantFile` | `KConfigGen` | Feature configuration JSON |

## Pipeline Step Lifecycle

Each step follows this lifecycle:

1. `get_inputs()` — declare input files for change detection
2. `run()` — execute the step's logic
3. `get_outputs()` — declare output files for change detection
4. `update_execution_context()` — modify the execution context for downstream steps (e.g., register environment variables, install paths)
