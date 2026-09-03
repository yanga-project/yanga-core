# Share Pipeline Fragments Between Configurations

A `yanga.yaml` pipeline can pull in the steps of another file with `include:`, so several
configurations share one definition instead of repeating it.

## Split a pipeline

Put the shared steps in a file with a top-level `pipeline:` key:

```yaml
# pipeline/bootstrap.yaml
pipeline:
  - step: CreateVEnv
    module: pypeline.steps.create_venv
  - step: PoksInstall
    module: yanga_core.steps.poks_install
```

Then include it. The included steps are spliced in **at the position of the entry**, so
where you put the `include:` decides where its steps run:

```yaml
# yanga.yaml
pipeline:
  - include: pipeline/bootstrap.yaml
  - step: GenerateBuildSystemFiles
    module: yanga.cmake.steps
  - step: ExecuteBuild
    module: yanga.cmake.steps
```

An include entry stands alone. Declaring `include:` together with `step:`, `module:`,
`file:` or `run:` in the same entry is an error.

## Where a fragment is looked up

The path is resolved in this order, and the first match wins:

1. next to the `yanga.yaml` that declares the `include:`
2. the project root
3. `platforms/`

That is the same lookup used for a variant's feature selection file and for a platform's
toolchain file, so a fragment can be named relative to the project root even from a
`yanga.yaml` nested under `variants/`:

```yaml
# variants/Disco/yanga.yaml
pipeline:
  - include: pipeline/bootstrap.yaml
```

If no candidate exists, the error names every path that was searched.

## Include only some steps

Give the object form to take named steps rather than the whole file. The steps run in the
order you list them:

```yaml
pipeline:
  - include:
      file: pipeline/bootstrap.yaml
      steps: [CreateVEnv]
```

An unknown step name is an error listing the names the fragment does define.

## What a fragment is not

A fragment holds yanga steps, which are typed to yanga's own execution context. The file
format is pypeline's, but such a fragment is only loadable through yanga; `pypeline run`
cannot execute it. A fragment that contains **only** steps from `pypeline.steps` is the
exception, and can be shared with a plain `pypeline.yaml`.

Fragments may include further fragments. A path inside a fragment is resolved relative to
that fragment. A cycle is reported rather than followed.
