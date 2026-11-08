# Generate an SPL Report

The SPL overview is one entry page for the whole product line: per variant and platform, what was built, from which commit, with links to its report and its artifacts, plus a link to the SPL documentation report. The variants are built in separate runs. Each run writes a publish manifest, and the overview is rendered from those manifests afterwards.

## Prerequisites

- Every variant build ends with `WritePublishManifest`, after the step that runs the build:

  ```yaml
  pipeline:
    build:
      - step: GenerateBuildSystemFiles
        module: yanga.cmake.steps
      - step: GenerateReportConfig
        module: yanga_core.steps.generate_report_config
      - step: ExecuteBuild
        module: yanga.cmake.steps
      - step: WritePublishManifest
        module: yanga_core.steps.write_publish_manifest
  ```

- The variants are built, for example `yanga run --variant Disco --platform gtest --target report` for each variant. A variant that was not built is not listed.
- The project root has the usual `conf.py` and `index.md`. `index.md` branches on `report_data.has_spl_scope` for the SPL documentation report.
- The project root has the overview template, `spl_overview.html.jinja` by default. See [`RenderSplOverview`](../reference/steps.md) for the data it gets.

## Pipeline configuration

Put the SPL steps in their own pypeline file, for example `spl_pypeline.yaml`:

```yaml
pipeline:
  - step: RegisterSplPaths
    description: Read the build directory settings from yanga.ini or pyproject.toml
    module: yanga_core.steps.register_spl_paths
  - step: GenerateSplReportConfig
    description: Write the report config that makes index.md render its SPL branch
    module: yanga_core.steps.generate_spl_report_config
    config:
      project_name: MySPL
  - step: SphinxBuildReport
    description: Build conf.py and index.md into .yanga/build/spl/reports
    module: yanga_core.steps.sphinx_build_report
  - step: WritePublishManifest
    description: Record the SPL documentation in .yanga/build/spl/publish_manifest.json
    module: yanga_core.steps.write_publish_manifest
  - step: CollectPublishManifests
    description: Read the manifests the variant builds left under .yanga/build/variants
    module: yanga_core.steps.collect_publish_manifests
  - step: RenderSplOverview
    description: Fill spl_overview.html.jinja and write .yanga/build/index.html
    module: yanga_core.steps.render_spl_overview
    config:
      project_name: MySPL
```

Run it with:

```bash
pypeline run --config-file spl_pypeline.yaml
```

Open `.yanga/build/index.html`. The build dir is the site root:

```
.yanga/build/
  index.html                                               <- SPL overview
  spl/reports/                                             <- SPL documentation report
  variants/<variant>/<platform>[/<build_type>]/reports/    <- variant reports
```

## How the pieces fit

1. A step that makes a file to publish registers a `PublishedFile`. `WritePublishManifest` writes the outputs that exist into `publish_manifest.json`, with links relative to the site root. Nothing is copied, so the overview links to the reports where the builds left them.
2. `RegisterSplPaths` reads the project settings once and registers the resolved `SPLPaths`; the other steps take no path configuration.
3. `GenerateSplReportConfig` and `SphinxBuildReport` render the SPL documentation report to `spl/reports/`. `WritePublishManifest` then writes the SPL manifest.
4. `CollectPublishManifests` finds all manifests on disk. A download step that runs before it (for example pypeline-semantic-release's `DownloadReleaseAssets`) restores outputs and manifests into the same layout, so the following step cannot tell a downloaded output from a local one.
5. `RenderSplOverview` renders the project's template to `index.html`.

See [Built-in Pipeline Steps](../reference/steps.md) for the configuration options of each step.
