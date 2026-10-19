# The Component Data Model and Its Lifecycle

A component's data passes through four dataclasses as it moves from a `yanga.yaml`
file to a generated build system. Each has **one owning module that creates it** and
a defined set of consumers. Keeping these roles distinct is what stops the project
slurper and the component resolver from bleeding into each other.

## The four dataclasses

| Dataclass | Module | Purpose |
| --- | --- | --- |
| `ComponentConfig` | `domain/config.py` | The wire model: one component exactly as declared in `yanga.yaml` (a `ConfigElement`, so it carries source `location`). Relative paths, raw strings, nothing resolved. |
| `ComponentsConfigsPool` | `domain/project_slurper.py` | All `ComponentConfig`s indexed by name. The slurper's parse-time registry, and a raw-config introspection surface. |
| `Component` | `domain/components.py` | A **self-contained declared record**: name, alias, root spec, sources, declared include directories, `required_components`. The domain representation, independent of the config layer and the filesystem. |
| `ResolvedComponent` | `domain/components.py` | A component with every path resolved to an absolute location: root, located sources, resolved include directories. Immutable. |

## Who creates each, and who uses it

| Dataclass | Created by | Used by |
| --- | --- | --- |
| `ComponentConfig` | config parsing (mashumaro deserialization of `yanga.yaml`, gathered by `config_slurper`) | `ComponentsConfigsPool`, `ComponentFactory`, the `info` / `info_schema` commands |
| `ComponentsConfigsPool` | `YangaProjectSlurper` (`_collect_components_configs`) | the slurper internally (`ComponentFactory`, subcomponent resolution); `info` / `info_schema`. **Not** the resolver, **not** the generators |
| `Component` | `ComponentFactory.create`, driven by the slurper | `ComponentResolver`; `ExecutionContext` (carries the selected components); any consumer that needs declared data |
| `ResolvedComponent` | `ComponentResolver.resolve`, at build-system generation | the CMake generators (with `ComponentAnalyzer` as a thin helper over them) |

## Lifecycle

```{mermaid}
flowchart LR
  yaml[yanga.yaml] -->|parse| cfg[ComponentConfig]
  cfg -->|index by name| pool[ComponentsConfigsPool]
  pool -->|ComponentFactory| comp[Component]
  comp -->|ComponentResolver, at gen| res[ResolvedComponent]
  res -->|read| gen[CMake generators]
```

1. **Parse** (slurper). `yanga.yaml` files are read into `ComponentConfig`s, indexed
   into a `ComponentsConfigsPool`.
2. **Declare** (slurper, via `ComponentFactory`). Each `ComponentConfig` becomes a
   self-contained `Component`. The slurper materializes the **full universe** of
   declared components; variant/platform selection only decides which ones are
   *built*, while resolution sees the whole universe so transitive
   `required_components` always resolve.
3. **Pipeline runs** (install, gen). Declared components are fixed. Components that
   are external or generated enter here, via the data registry, not the slurper.
4. **Resolve** (`ComponentResolver`, at generation). Each `Component` becomes a
   `ResolvedComponent`: root, sources, and include directories resolved against the
   universe plus the execution context. Resolution is memoized per component.
5. **Consume** (CMake generators). Generators read `ResolvedComponent`s.

## The responsibility boundary

- **Project slurper** owns *parse* and *declare*. It creates `ComponentConfig`, the
  `ComponentsConfigsPool`, and `Component`. The pool is an implementation detail of
  this phase; it is **never handed to the resolver or the generators** (only the
  `info` commands read it, for raw-config introspection).
- **Component resolver** owns *resolve*. Its inputs are `Component`s plus the
  execution context; its output is `ResolvedComponent`. It knows nothing about
  `yanga.yaml`, `ComponentConfig`, or the pool.

This is why `Component` must be a *complete* declared record: if it omitted
`required_components` or its declared include directories, the resolver would have to
reach back into the pool, and the parse and resolve responsibilities would blur. A
self-contained `Component` is the seam that keeps them apart.

See [design decisions](design-decisions.md) for *why* resolution is lazy and
consumption-time.

## Container and integration components

A component that lists `subcomponents` is a **container**: it groups other
components for selection. A component that lists `integrates` is an
**integration component**: it compiles other components' sources again, for
example for an integration test.

```yaml
components:
  - name: networking
    subcomponents: [tcp, transport, pins]
  - name: test_networking
    integrates: [networking]
    testing:
      sources: [test/test_networking.cc]
```

- **Selecting a container** selects it and its subcomponents, depth first, in
  declared order. `ComponentResolver` does the expansion, so
  `selected_components` is already expanded. A container has no `sources`,
  `include_directories` or `testing` of its own.
- **Duplicates fail.** A component selected directly and through a container, or
  through two containers, is an error that names both ways.
- **Requiring a container** gives the public include directories of all its
  subcomponents. A container may have its own `required_components`;
  their public include directories are added to the container's.
- **An integration component** does not select what it integrates. Its resolved
  `sources` are its own plus those of every integrated component (a container
  stands for all its subcomponents), and its include directories add theirs,
  private ones and source folders included.
- **Aliases.** A `subcomponents` or `integrates` entry may be an alias. If the
  platform already selected a component with that alias, that one is used.
  Otherwise the one declared component with that alias is used; several
  candidates is an error.

See [design decisions](design-decisions.md) for why these are two concepts.
