---
status: Done (2026-11-20)
priority: Medium
related: [YCORE-002]
---

# [YCORE-003] Resolved component keeps what it integrates

## Summary

As the developer of a build backend, I want the resolved component to say which components it integrates, and one function that finds the testing block of a framework, so that a backend that links several selected components into one test leaves integration components out without guessing, and every framework generator finds its block the same way.

## Description

An integration component (`integrates`) compiles the sources of other components a second time for its own test, without selecting them. The resolver adds the integrated sources to the integration component's `sources` and then drops the names, so the resolved `Component` no longer says that it is an integration component.

yanga's variant test links the objects of every selected component. An integration component is selected too (on the test platform), and its objects are second copies of the components it integrates, so linking it defines their symbols twice. yanga must leave it out, and today it can only guess by comparing source sets. The design decision "A build backend needs no special case" no longer holds for that backend.

A framework generator also needs "the testing block of my framework" for a component and for the variant. yanga-core offers `is_testable(framework)` but no lookup, so each generator writes it again.

## Scope decisions

- **`integrates` on the resolved component.** A list of the resolved names of the integrated components, as the resolver already resolves them for the sources: aliases resolved, a container replaced by its subcomponents. Empty for any other component. No `is_integration` property: an empty list says the same.
- **One lookup function** for the block of a framework in a list of resolved testing blocks. It serves components and the variant; no separate method on the execution context.
- **No new check for a component with both `subcomponents` and `integrates`.** Tests on a container with `integrates` are a later idea, so that combination is not refused now.
- Out of scope: moving `MockingConfig` out of yanga-core, tests on containers, the yanga change that uses this.

## Acceptance criteria

- [x] A resolved integration component lists the names of the components it integrates, with an alias resolved to the component name and a container replaced by its subcomponents
- [x] A resolved component without `integrates` has an empty list
- [x] The lookup returns the block of the given framework, and nothing for a list without that framework or an empty list
- [x] The design decision on integration components says that a backend linking several selected components into one executable leaves integration components out, and the component model and domain reference describe the new field and the lookup
- [x] `pypeline run` is green

## Plan

1. **`Component.integrates`.** Add the field in `src/yanga_core/domain/components.py`; in `ComponentResolver._resolve` (`component_resolver.py`) fill it from the list `_integrated_components` already returns for the sources. Check: in `tests/test_component_resolver.py`, the existing tests for an ordinary component, an integration of one component, of a container, and an entry by alias also check `integrates`.
2. **`find_testing_block(blocks, framework)`.** Add it next to `resolve_testing_blocks` in `component_resolver.py`. Check: one parametrized test (found, other framework only, empty list).
3. **Docs.** `docs/explanation/design-decisions.md` (Integration components), `docs/explanation/component-model.md` (integration components and testing blocks), `docs/reference/domain-model.md` (resolved `Component`). Check: the Docs step of `pypeline run`.
4. **Gate.** `git add -A`, then `pypeline run`. Check: green.
