from yanga_core.domain.config import BuildTargets, PlatformConfig


def test_build_targets_defaults_are_empty() -> None:
    bt = BuildTargets()
    assert bt.generic == []
    assert bt.variant == []
    assert bt.component == []
    assert bt.variant_targets == []
    assert bt.component_targets == []


def test_build_targets_effective_sets_combine_generic_and_scope() -> None:
    bt = BuildTargets(generic=["all"], variant=["docs"], component=["unit_tests"])
    assert bt.variant_targets == ["all", "docs"]
    assert bt.component_targets == ["all", "unit_tests"]


def test_build_targets_effective_sets_dedupe_preserve_order() -> None:
    bt = BuildTargets(generic=["all", "build"], variant=["build", "docs"], component=["all", "unit_tests"])
    assert bt.variant_targets == ["all", "build", "docs"]
    assert bt.component_targets == ["all", "build", "unit_tests"]


def test_platform_config_bare_list_applies_to_both_scopes() -> None:
    p = PlatformConfig.from_dict({"name": "host", "build_targets": ["all", "docs"]})
    assert p.variant_build_targets == ["all", "docs"]
    assert p.component_build_targets == ["all", "docs"]


def test_platform_config_dataclass_form_splits_scopes() -> None:
    p = PlatformConfig.from_dict(
        {
            "name": "host",
            "build_targets": {
                "generic": ["all"],
                "variant": ["docs"],
                "component": ["unit_tests"],
            },
        }
    )
    assert p.variant_build_targets == ["all", "docs"]
    assert p.component_build_targets == ["all", "unit_tests"]


def test_platform_config_dataclass_form_partial_keys() -> None:
    p = PlatformConfig.from_dict({"name": "host", "build_targets": {"component": ["unit_tests"]}})
    assert p.variant_build_targets == []
    assert p.component_build_targets == ["unit_tests"]


def test_platform_config_missing_build_targets_returns_empty() -> None:
    p = PlatformConfig.from_dict({"name": "host"})
    assert p.build_targets is None
    assert p.variant_build_targets == []
    assert p.component_build_targets == []
