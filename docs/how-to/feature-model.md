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

### 3. Reference in the Variant

```yaml
variants:
  - name: ConnectedProduct
    components: [main, networking]
    features_selection_file: "config.txt"
```

### 4. Add KConfigGen to the Pipeline

```yaml
pipeline:
  - gen:
    - step: KConfigGen
      module: yanga_core.steps.kconfig_gen
```

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
