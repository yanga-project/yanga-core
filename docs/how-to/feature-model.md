# Use KConfig Feature Models

yanga-core treats feature models as a first-class SPL concept. The `KConfigGen` step processes KConfig definitions to generate C headers, JSON configs, and feature documentation.

## Set Up a Feature Model

### 1. Create a KConfig File

Place a `KConfig` file in your project (typically at the root or in a dedicated directory):

```kconfig
menu "Networking"

config NETWORKING_ENABLED
    bool "Enable networking support"
    default y

config MAX_CONNECTIONS
    int "Maximum number of connections"
    default 10
    depends on NETWORKING_ENABLED

endmenu
```

### 2. Create a Feature Selection File

For each variant, create a selection file (e.g., `config.txt`) that sets feature values:

```
CONFIG_NETWORKING_ENABLED=y
CONFIG_MAX_CONNECTIONS=20
```

### 3. Declare the Model and Reference the Selection

```yaml
feature_model:
  description: Product features
  file: KConfig

variants:
  - name: MyVariant
    components: [main, networking]
    feature_selection:
      file: "config.txt"
```

See the [configuration reference](../reference/configuration.md#feature-models-and-selections) for platform models and per-platform selections.

### 4. Add KConfigGen to the Pipeline

```yaml
pipeline:
  - gen:
    - step: KConfigGen
      module: yanga_core.steps.kconfig_gen
```

## Edit the Selection

Give the model a pipeline that ends with `KConfigEdit`. Steps before it prepare what the model needs, for example a variable the `KConfig` file reads:

```yaml
feature_model:
  description: Product features
  file: KConfig
  pipeline:
    - include: pipeline/bootstrap.yaml
    - step: KConfigEdit
      module: yanga_core.steps.kconfig_edit
```

Then open the editor for a variant, or the viewer for all variants:

```bash
yanga features --variant MyVariant          # GUI
yanga features --variant MyVariant --no-gui # terminal
yanga features                                     # all variants side by side
```

The editor saves to the variant's `config.txt`.

A platform with a KConfig model of its own declares a `feature_model:` block the same way, and `yanga features --variant MyVariant --platform <NAME>` runs it, editing the variant's `platforms.<NAME>.feature_selection` file. `--platform` without a variant is an error.

That platform pipeline ends with `KConfigEdit` only when plain kconfiglib can load the model. A framework whose model needs its own tooling declares that tooling instead: Zephyr's Kconfig tree, for instance, uses Zephyr's own kconfiglib fork plus an environment that its CMake configure computes, so its editor is the `menuconfig` build target of a variant's build, and the pipeline also carries whatever writes the result back into the selection file.

## Generated Outputs

`KConfigGen` produces three files in `<variant_build_dir>/kconfig/`:

| File | Purpose |
|------|---------|
| `autoconf.h` | C header with `#define` macros for each selected feature |
| `autoconf.json` | JSON representation of the full configuration |
| `autoconf.md` | Markdown documentation of the feature selection |

The output directory is automatically registered as a global public include artifact via `data_registry`, making `autoconf.h` available to all components.

## Use Features in C Code

```c
#include "autoconf.h"

#if defined(CONFIG_NETWORKING_ENABLED)
void init_networking(void) {
    setup_connections(CONFIG_MAX_CONNECTIONS);
}
#endif
```

## Feature Documentation

The generated `autoconf.md` contains a formatted table of all features with their types, values, and macro names. This file is registered as a `FeaturesReportRelevantFile` in `data_registry` and included in variant reports by the `GenerateReportConfig` step.
