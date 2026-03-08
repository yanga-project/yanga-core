# Create a Custom Pipeline Step

yanga-core's pipeline is extensible. You can create custom steps by subclassing `PipelineStep` and referencing them in your `yanga.yaml`.

## Step Structure

A pipeline step is a Python class that receives an `ExecutionContext` and implements `run()`:

```python
from pathlib import Path
from pypeline.domain.pipeline_step import PipelineStep
from yanga_core.domain.execution_context import ExecutionContext


class MyCustomStep(PipelineStep[ExecutionContext]):
    def run(self) -> None:
        ctx = self.execution_context
        # Access project paths
        build_dir = ctx.spl_paths.variant_build_dir
        # Access components
        for component in ctx.components:
            self.logger.info(f"Processing {component.name}")
        # Access the data registry for inter-step communication
        # ctx.data_registry.get(SomeType)

    def get_inputs(self) -> list[Path]:
        """Files that trigger re-execution when changed."""
        return list(self.execution_context.user_config_files)

    def get_outputs(self) -> list[Path]:
        """Files produced by this step."""
        return []
```

## Register the Step

Reference your step in `yanga.yaml` by its class name and module path:

```yaml
pipeline:
  - custom:
    - step: MyCustomStep
      module: my_project.steps.my_custom_step
```

The module must be importable from the Python path.

## Inter-Step Communication via `data_registry`

Steps communicate through `ExecutionContext.data_registry`. A step can publish data for downstream steps:

```python
from yanga_core.domain.artifact import Artifact

class ProducerStep(PipelineStep[ExecutionContext]):
    def run(self) -> None:
        artifact = Artifact(
            path=self.output_dir / "generated" / "output.h",
            provider="ProducerStep",
            consumers=None,       # None = available to all components
            labels=["include", "public"],
        )
        self.execution_context.data_registry.append(artifact)
```

A downstream step retrieves published data:

```python
from yanga_core.domain.artifact import Artifact, filter_artifacts, with_label

class ConsumerStep(PipelineStep[ExecutionContext]):
    def run(self) -> None:
        all_artifacts = self.execution_context.data_registry.get(Artifact)
        include_artifacts = filter_artifacts(with_label("include"))(all_artifacts)
```

## Access Configuration

Use `collect_configs_by_id` to read configs declared in variants, platforms, or the project:

```python
from yanga_core.domain.config_utils import collect_configs_by_id

class MyStep(PipelineStep[ExecutionContext]):
    def run(self) -> None:
        configs = collect_configs_by_id(self.execution_context, "my_tool")
        for config in configs:
            # config.content or config.file
            ...
```

## Smart Re-execution

yanga-core's scheduler compares `get_inputs()` and `get_outputs()` to decide if a step needs re-execution. Return meaningful file lists to avoid unnecessary rebuilds:

- `get_inputs()` — return files your step reads (config files, source files)
- `get_outputs()` — return files your step produces (generated code, artifacts)
