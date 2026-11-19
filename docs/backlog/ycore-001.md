---
status: Open
priority: Medium
---

# [YCORE-001] Keep external and the own sources on the resolved component

## Summary

The resolved component says which external project it comes from and which of its sources it declares itself, so that a static analysis report can name the external project of a finding and analyse each source only under the component that declares it.

## Description

The resolved `Component` loses two facts that its config has. First, `ComponentConfig.external` is used to find the component's path but is not kept on the component, so a report cannot say that a component comes from an external project. Second, an integration component (`integrates:`) adds the sources of the components it integrates to its own `sources`, so a consumer cannot tell its own sources from the integrated ones. yanga's clang-tidy generator therefore analyses the integrated product files again under the integration component, and the report lists their findings twice. This is the yanga-core part of a change across yanga-core and yanga; the design is in the planning vault's epic SB-005.

## Scope decisions

- **Typed fields, no dynamic metadata.** The report and the analysis depend on them, so they stay typed.
- **`external`.** The resolved component carries the name of its external project, or none, copied from its config.
- **Own sources apart from integrated ones.** `sources` keeps its meaning (every source the component compiles, integrated ones included), so the build does not change. The component also records which of them it declares itself.
- **Subcomponents.** A subcomponent's `external` is its own config value; nothing is inherited.
- Out of scope: `is_platform_component` (not needed for the analysis on one platform), any change to how integrated sources are compiled.

## Acceptance criteria

- [ ] A component from an external project carries that project's name; an in-tree component carries none
- [ ] An integration component's own sources exclude the sources of the components it integrates, a container standing for all its subcomponents
- [ ] A component that integrates nothing has the same own sources as `sources`
- [ ] `sources` of an integration component is unchanged
- [ ] The new fields are documented in the API reference
- [ ] `pypeline run` is green
