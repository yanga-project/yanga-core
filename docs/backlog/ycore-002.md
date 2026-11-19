---
status: Ready
priority: Medium
---

# [YCORE-002] Testing blocks per framework on components and variants

## Summary

As a developer of a product line, I want to declare tests per test framework on a component and on a variant, so that one component or variant can carry tests for several frameworks (gtest, TESSY, a virtual ECU) and each platform builds only the tests its generators can run.

## Description

Today tests exist only on a component, in `testing.sources` or the older `test_sources`, and every test source is treated as a GoogleTest source. A variant has no testing field, so a test of the whole variant needs a workaround: an extra integration component that is listed again in every variant. Test-only helper code has no place either: in the production sources it counts for coverage, and in the test sources the generated mocks clash with the symbols it defines. This is the yanga-core part of a change across yanga-core and yanga; the design is in the planning vault's epic SB-006.

## Scope decisions

- **`testing` is a list of blocks, one per framework.** Each block has `framework` (always written), `sources` (the test code), `mockup_sources` (test-only helpers) and `config` (a free dict). One list has at most one block per framework; a second block for the same framework is refused.
- **yanga-core does not know the frameworks.** `framework` is a plain string and `config` is passed on as it is; the generator of that framework reads it into its own dataclass, the way a platform's generator entry already has a `config`.
- **Same blocks on a variant.** `VariantConfig` gets the same `testing` field. The variant's resolved blocks are available to the generators of a run. A variant's source paths are found like its feature selection: next to the variant's file, then in the project root.
- **The old forms are dropped.** `TestingConfig` and the `test_sources` field are removed from the config, with no check of their own: a leftover `test_sources` key is ignored like any unknown key. yanga-core is at 0.x, so this ships as a normal minor release.
- **The resolved component carries the blocks.** `Component.testing` becomes the list of resolved blocks. `Component.test_sources` lists the sources of all blocks. `Component.is_testable(framework=None)` becomes a method: without an argument it says whether any block has sources, with a framework name whether that framework's block has. yanga changes with it in YANGA-004; yanga is in alpha, so its breaking change needs no major version.
- Out of scope: test sources per platform on a variant, a closed list of framework names, removing the integration component.

## Acceptance criteria

- [ ] A component and a variant accept `testing` as a list of framework blocks with `framework`, `sources`, `mockup_sources` and `config`
- [ ] A block without `framework` is refused with a message that names the component or variant
- [ ] Two blocks with the same framework in one list are refused with a message that names the component or variant and the framework
- [ ] The resolved component carries its blocks, with source and mockup source paths under the component root
- [ ] `is_testable()` is true when any block has sources; `is_testable("gtest")` only when the `gtest` block has sources
- [ ] The generators of a run can read the resolved blocks of the selected variant, with paths found next to the variant's file, then in the project root
- [ ] A variant without `testing` resolves exactly as today
- [ ] The component model documentation describes the testing blocks
- [ ] `pypeline run` is green

## Refinement notes

Findings from reading the code on 2026-11-19 (branch `feat/collect-reads-disk-only`, 0.13.1 plus one commit; `main` is at 0.14.2 and has not changed the code this item touches).

- **Where the config checks go.** An error raised while a field is decoded loses its message (the existing comment on `YangaUserConfig.__pre_deserialize__`). The two checks (missing `framework`, repeated framework) therefore go next to the existing `features_selection_file` check in `YangaUserConfig.__pre_deserialize__`, which sees the component and variant names. A `ComponentConfig` built in Python is not checked; that is the calling code's responsibility.
- **No union type.** A probe showed that a union `list[TestingBlock] | TestingConfig` decodes a block without `framework` silently to `testing: None`. With the old forms dropped, the field is `list[TestingBlock]` only.
- **What the removed forms do.** A probe showed: a leftover `test_sources` key is ignored, so its tests are no longer built. A leftover old `testing` dict is not ignored, because the `testing` key still exists: loading fails with mashumaro's own error, `Field "testing" of type list[TestingBlock] in ComponentConfig has invalid value {...}`.
- **What yanga reads today.** `component.test_sources` (gtest generator and report config), `component.is_testable` as a property (gtest generator) and `component.testing.mocking` (gtest generator). The last two change; YANGA-004 adapts them.
- **Where the variant's blocks live.** `ExecutionContext.variant` already holds the `VariantConfig`; `variant_feature_selection_file` is the pattern for a resolved value. `ExecutionContext.variant_testing` follows it. `locate_artifact` fails on a missing file, which is the wanted behaviour.
- **The container check.** `_subcomponent_names` refuses a container with `testing`; an empty list still counts as no testing. Its `test_sources` part goes away with the field.
- **`MockingConfig` stays.** yanga-core no longer uses it, but yanga imports it and reads the gtest block's `config["mocking"]` into it.

### Risks

- **The current yanga breaks on this release.** yanga allows `yanga-core<1`, so a fresh install of the current yanga picks it up and fails on `component.is_testable` and `component.testing.mocking`. Accepted: yanga is in alpha, and YANGA-004 follows.
- **The vault still describes the old forms.** The epic SB-006 and the design note say the old form is read as `gtest`. They need the same update; that is vault work, outside this repository.
- **The docs are stale already.** `docs/reference/domain-model.md` names a type `TestingConfiguration` that does not exist.

### Dependencies

- Blocks YANGA-004 and YANGA-005 (SB-006).
- Work starts from `main`, not from `feat/collect-reads-disk-only`.

## Plan

1. **Config model.** Add `TestingBlock(ConfigElement)` with `framework`, `sources`, `mockup_sources`, `config: dict[str, Any]`. `ComponentConfig.testing` and a new `VariantConfig.testing` become `list[TestingBlock]` (default empty). Remove `TestingConfig` and `ComponentConfig.test_sources`; keep `MockingConfig`. Touches `src/yanga_core/domain/config.py`. Check: a test that reads a component and a variant with two blocks through `YangaUserConfig.from_dict`.
2. **Config checks.** In `YangaUserConfig.__pre_deserialize__`, refuse a block without `framework` and a repeated framework, each message naming the component or variant. Touches `config.py`. Check: one parametrized test over both cases, for a component and a variant, matching the message.
3. **Resolved blocks on the component.** Add a resolved block type (framework, located `sources` and `mockup_sources`, `config`). `Component.testing` becomes a list of it, `test_sources` a property over all blocks, `is_testable(framework=None)` a method. Replace `_declared_test_sources` in the resolver with a function that returns the blocks with paths under the component root, and drop `test_sources` from the container check. Touches `components.py`, `component_resolver.py`, `tests/test_component_resolver.py` (its `TestingConfig` uses). Check: parametrize `test_is_testable_reflects_declared_test_sources` over no framework, a matching and a missing framework; a test for `mockup_sources` paths; the container test keeps passing.
4. **Variant blocks for generators.** Add `ExecutionContext.variant_testing`, the variant's resolved blocks with paths found by `locate_artifact` next to the variant's file, then in the project root; empty when there is no variant or no `testing`. Touches `execution_context.py`. Check: a test with a variant with blocks and one without.
5. **Docs.** Describe the blocks and the variant field in `docs/explanation/component-model.md` (including the container and integration example, which uses the old form), and fix the `testing` rows in `docs/reference/domain-model.md`. Check: `pypeline run` builds the docs.
6. **Gate.** `git add -A`, then `pypeline run` green.
