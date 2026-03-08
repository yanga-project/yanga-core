# Create a Product Variant

Variants are the central concept in Software Product Line engineering. Each variant represents a specific product configuration built from a set of components.

## Basic Variant

A minimal variant requires a name and a list of components:

```yaml
variants:
  - name: MyProduct
    description: A basic product variant
    components:
      - main
      - networking
      - storage
```

## Feature Selection

For SPLs with KConfig feature models, specify a feature selection file to control which features are enabled:

```yaml
variants:
  - name: PremiumProduct
    components: [main, networking, storage, premium_features]
    features_selection_file: "config_premium.txt"
```

The `KConfigGen` step reads this file, processes the KConfig model, and generates:
- `autoconf.h` — C header with `#define` macros for selected features
- `autoconf.json` — JSON representation of the configuration
- `autoconf.md` — Markdown documentation of the feature selection

## Generic Configuration Variables

Pass custom key-value pairs to the build system using `configs` with `id: vars`:

```yaml
variants:
  - name: DebugVariant
    components: [main]
    configs:
      - id: vars
        content:
          MY_CUSTOM_FLAG: "enabled"
          BUILD_NUMBER: 123
```

## Platform-Specific Overrides

Override variant settings for specific platforms. This is useful when a variant needs different components or configuration on different targets:

```yaml
variants:
  - name: MyProduct
    components: [main, core_lib]
    platforms:
      arm_target:
        components: [hal_arm, bsp_arm]
        configs:
          - id: vars
            content:
              PLATFORM_SPECIFIC_FLAG: "true"
      x86_host:
        components: [hal_x86]
```

When building `MyProduct` for `arm_target`, the final component list is `[main, core_lib, hal_arm, bsp_arm]`. Platform-specific components are appended to the base list.

## Variant Dependencies

Variants can declare external dependencies via `configs` with `id: west` or `id: poks`. See [Configure External Dependencies](configure-dependencies.md).
