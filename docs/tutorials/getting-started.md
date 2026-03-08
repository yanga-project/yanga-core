# Getting Started with yanga-core

yanga-core is a Python framework for building SPL (Software Product Line) tooling. It provides project discovery, configuration parsing, pipeline orchestration, and reusable steps — your application supplies the build-system-specific logic.

This tutorial shows how to use yanga-core programmatically in a Python application.

## Prerequisites

Install yanga-core:

```bash
pip install yanga-core
```

## Discover and Load a Project

Use `YangaProjectSlurper` to scan a project directory for `yanga.yaml` files and resolve the full configuration:

```python
from pathlib import Path
from yanga_core.domain.project_slurper import YangaProjectSlurper

slurper = YangaProjectSlurper(
    project_dir=Path("/path/to/my-project"),
    configuration_file_name="yanga.yaml",
    exclude_dirs=[],
    create_yanga_build_dir=True,
)

# Inspect discovered configuration
for variant in slurper.variants:
    print(f"Variant: {variant.name}, components: {variant.components}")

for platform in slurper.platforms:
    print(f"Platform: {platform.name}")
```

## Resolve Components for a Variant

Retrieve the full component list for a variant+platform combination, including platform-specific additions and transitive include directory resolution:

```python
components = slurper.get_variant_components(
    variant_name="MyProduct",
    platform_name="native",
)

for component in components:
    print(f"  {component.name}: {component.sources}")
    for inc in component.include_dirs:
        print(f"    include: {inc.path} ({inc.scope})")
```

## Create an ExecutionContext

The `ExecutionContext` is the central runtime object passed to all pipeline steps. It holds the resolved variant, platform, components, and path conventions:

```python
from yanga_core.domain.execution_context import (
    ExecutionContext,
    UserRequest,
    UserRequestScope,
    UserRequestTarget,
)

user_request = UserRequest(
    scope=UserRequestScope.VARIANT,
    variant_name="MyProduct",
    component_name=None,
    target=UserRequestTarget.ALL,
    build_type="Debug",
)

context = ExecutionContext(
    project_root_dir=Path("/path/to/my-project"),
    user_request=user_request,
    variant_name="MyProduct",
    components=components,
    user_config_files=slurper.user_config_files,
    features_selection_file=slurper.get_variant_config_file("MyProduct"),
    platform=slurper.get_platform("native"),
    variant=slurper.get_variant_config("MyProduct"),
    project_configs=slurper.project_configs,
    create_yanga_build_dir=True,
)

# Access resolved paths
print(f"Build dir: {context.spl_paths.variant_build_dir}")
print(f"External deps: {context.spl_paths.external_dependencies_dir}")
```

## Use the Data Registry

Steps communicate through the `data_registry`. You can publish and consume typed data:

```python
from yanga_core.domain.artifact import Artifact, filter_artifacts, with_label

# Publish an artifact
artifact = Artifact(
    path=Path("/output/generated/config.h"),
    provider="MyGenerator",
    consumers=None,  # available to all components
    labels=["include", "public"],
)
context.data_registry.append(artifact)

# Query artifacts downstream
all_artifacts = context.data_registry.get(Artifact)
include_dirs = filter_artifacts(with_label("include"))(all_artifacts)
```

## Collect Configuration by ID

Use `collect_configs_by_id` to gather typed configuration entries from variants, platforms, and the project level:

```python
from yanga_core.domain.config_utils import collect_configs_by_id

west_configs = collect_configs_by_id(context, "west")
for config in west_configs:
    print(f"West config from {config.source_file}: {config.content}")
```

## Next Steps

- [Configure external dependencies](../how-to/configure-dependencies.md) with West or Poks
- [Create custom pipeline steps](../how-to/create-custom-step.md)
- Understand the [Architecture](../explanation/architecture.md) and layered design
- Read the [API Reference](../reference/api.md) for the full Python API
