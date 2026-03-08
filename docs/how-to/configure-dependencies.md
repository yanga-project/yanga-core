# Configure External Dependencies

yanga-core provides built-in pipeline steps for acquiring external dependencies using West or Poks. Dependencies are declared in `yanga.yaml` using the `configs` mechanism with well-known `id` strings.

## West (Git Repository Dependencies)

Use `WestInstall` to clone and update Git repositories via [Zephyr West](https://docs.zephyrproject.org/latest/develop/west/index.html).

### Step Configuration

Add `WestInstall` to your pipeline:

```yaml
pipeline:
  - install:
    - step: WestInstall
      module: yanga_core.steps.west_install
```

### Declare Dependencies

Add a `configs` entry with `id: west` to a variant or platform:

```yaml
variants:
  - name: MyVariant
    components: [main]
    configs:
      - id: west
        content:
          remotes:
            - name: gtest
              url-base: https://github.com/google
          projects:
            - name: googletest
              remote: gtest
              revision: v1.16.0
              path: gtest
```

Platform-specific dependencies are also supported:

```yaml
platforms:
  - name: my_platform
    configs:
      - id: west
        content:
          remotes:
            - name: my-remote
              url-base: https://github.com/my-org
          projects:
            - name: my-library
              remote: my-remote
              revision: v2.1.0
              path: vendor/my-library
```

`WestInstall` merges manifests from all matching configs (project, variant, platform, variant-platform) in priority order.

## Poks (Cross-Platform Package Manager)

Use `PoksInstall` for cross-platform tool installation (Windows, Linux, macOS). Tools are installed into `~/.poks/` and their paths are automatically available to subsequent pipeline steps.

### Step Configuration

```yaml
pipeline:
  - install:
    - step: PoksInstall
      module: yanga_core.steps.poks_install
```

### Declare Dependencies

```yaml
platforms:
  - name: nrf52
    configs:
      - id: poks
        content:
          buckets:
            - name: tools
              url: https://github.com/example/poks-bucket.git
          apps:
            - name: arm-gnu-toolchain
              version: "13.2.1"
              bucket: tools
```

## Config Merging Order

When multiple config sources declare the same `id`, yanga-core merges them in this order (later entries take precedence for conflicts):

1. Project-level configs
2. Variant configs
3. Platform configs
4. Variant-platform-specific configs
