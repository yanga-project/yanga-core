---
status: Done (2026-11-20)
priority: Medium
related: [YCORE-003]
---

# [YCORE-001] Keep external and the own sources on the resolved component

## Summary

The resolved component says which external project it comes from and which of its sources it declares itself, so that a static analysis report can name the external project of a finding and analyse each source only under the component that declares it.

## Description

The resolved `Component` loses two facts that its config has. First, `ComponentConfig.external` is used to find the component's path but is not kept on the component, so a report cannot say that a component comes from an external project. Second, an integration component (`integrates:`) adds the sources of the components it integrates to its own `sources`, so a consumer cannot tell its own sources from the integrated ones. YCORE-003 added `integrates`, the names of the integrated components, but not their files: an integrated component need not be selected by the variant, so a consumer cannot always look its files up by name. yanga's clang-tidy generator therefore analyses the integrated product files again under the integration component, and the report lists their findings twice. This is the yanga-core part of a change across yanga-core and yanga; the design is in the planning vault's epic SB-005.

## Scope decisions

- **Typed fields, no dynamic metadata.** The report and the analysis depend on them, so they stay typed.
- **`external`.** The resolved component carries the name of its external project, or none, copied from its config.
- **Own sources apart from integrated ones (decided 2026-11-20).** `sources` keeps its meaning (every source the component compiles, integrated ones included), so the build does not change. A new field `own_sources`, next to `integrates`, holds the sources the component declares itself. The resolver fills it once, when it resolves the component, before it adds the integrated sources; it is a stored list, not computed on access. The alternative, yanga removing the files of the components named in `integrates`, was rejected: it fails when the variant does not select an integrated component, and it works out files by comparing lists, which YCORE-003 avoids.
- **Subcomponents.** A subcomponent's `external` is its own config value; nothing is inherited.
- **Field name (decided 2026-11-20).** `own_sources`, next to `integrates`.
- **Docs (decided 2026-11-20).** The same three pages YCORE-003 changed: the domain model reference gets both new fields; the component model's "Container and integration components" says that `own_sources` holds an integration component's own files; the design decision "Integration components" says that a consumer that must not see integrated files twice, such as static analysis, reads `own_sources`. `external` gets only the reference line.
- Out of scope: `is_platform_component` (not needed for the analysis on one platform), any change to how integrated sources are compiled.

## Acceptance criteria

- [x] A component from an external project carries that project's name; an in-tree component carries none
- [x] An integration component's `own_sources` exclude the sources of the components it integrates, a container standing for all its subcomponents
- [x] A component that integrates nothing has `own_sources` equal to `sources`
- [x] `sources` of an integration component is unchanged
- [x] The new fields are documented in the API reference
- [x] `pypeline run` is green

## Plan

**Goal:** the resolved `Component` keeps `external` and `own_sources`. **Spec:** this item.

### Global Constraints

The general rubric, verbatim:

- **Asked for.** Every changed line traces to the item. No feature, option or clean-up the item did not ask for.
- **Existing pattern.** The change does what the repository already does in the same way. No second way of doing one thing.
- **Smallest form.** No abstraction with a single caller, no configuration for a value that never changes, no code for a state that cannot occur.
- **Names.** A name says what the thing is, in the words of the item and the repository.
- **Checks kept.** Validation and safety checks stay, above all at untrusted input, authentication and secrets.
- **Tests that matter.** The tests check the behaviour the acceptance criteria name, not the implementation's details.
- **Docs.** A feature a user can call ships its usage docs. A comment says why or when, not how.
- **Nothing private.** No personal data and no detail of a private setup in a file, a message or a test, also where no pattern scan would catch it.

The repository has no `docs/rubric.md`. Repository rules: `AGENTS.md` (tests with `pytest`, gate `pypeline run`, stage everything before it).

### Review Focus

- A container component: `own_sources` is its declared `sources` (empty), not those of its subcomponents.
- `own_sources` is deduplicated in the same way as `sources`.
- A subcomponent of an external container keeps its own `external` value, nothing inherited.

### Task 1.a (tester): tests for the two fields

Files: `tests/test_component_resolver.py`. Extend the existing tests, as YCORE-003 did for `integrates`:

- `test_component_without_dependencies`: `compC.own_sources == compC.sources` and `compC.external is None`.
- `test_external_component_root_resolves_from_registry`: `component.external == "ArduinoCoreAvr"`.
- `test_integration_component_compiles_integrated_sources_without_selecting_them`: `test_net.own_sources == [Path("prj/root/itest/stub.c")]`, and `sources` stays as asserted today.
- `test_container_selection_expands_nested_subcomponents_in_order` (or the closest container test): the container `networking` has `own_sources == []`.

Run `.venv/bin/python -m pytest tests/test_component_resolver.py`: the new assertions fail with `AttributeError`. Commit `test: own_sources and external on the resolved component (YCORE-001)`.

### Task 1.b (implementer): the fields

Files: `src/yanga_core/domain/components.py`, `src/yanga_core/domain/component_resolver.py`.

- `Component.own_sources: list[Path]` (default empty list, placed next to `sources`, with a `#:` comment) and `Component.external: str | None = None`.
- `ComponentResolver._resolve`: `own_sources` from the declared sources before the integrated ones are added, deduplicated like `sources`; `external=config.external`.

Run the same pytest command: green. No change to the files of 1.a.

### Task 2: docs

Files: `docs/reference/domain-model.md` (both fields, in the list of resolved `Component` fields), `docs/explanation/component-model.md` ("Container and integration components": `own_sources` holds an integration component's own files), `docs/explanation/design-decisions.md` ("Integration components": a consumer that must not see integrated files twice, such as static analysis, reads `own_sources`). Checked by the Docs step of the gate.

### Gate

`git add -A`, then `pypeline run`.
