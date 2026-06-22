from pathlib import Path

from yanga_core.domain.config import ComponentConfig, PlatformConfig, VariantConfig, VariantPlatformsConfig
from yanga_core.domain.project_slurper import ComponentsConfigsPool, YangaProjectSlurper


def test_collect_selected_component_names_with_platform_specific(tmp_path: Path) -> None:
    project_dir = tmp_path

    components_pool = ComponentsConfigsPool()
    components_pool["base_component"] = ComponentConfig(name="base_component", sources=["base.c"])
    components_pool["platform_component"] = ComponentConfig(name="platform_component", sources=["platform.c"])

    variant = VariantConfig(
        name="test_variant",
        components=["base_component"],
        platforms={"test_platform": VariantPlatformsConfig(components=["platform_component"])},
    )

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components_configs_pool = components_pool

    names_with_platform = project_slurper._collect_selected_component_names(variant, "test_platform")
    assert "base_component" in names_with_platform
    assert "platform_component" in names_with_platform
    assert len(names_with_platform) == 2

    names_without_platform = project_slurper._collect_selected_component_names(variant, None)
    assert names_without_platform == ["base_component"]

    names_different_platform = project_slurper._collect_selected_component_names(variant, "other_platform")
    assert names_different_platform == ["base_component"]


def test_collect_selected_component_names_no_platform_config(tmp_path: Path) -> None:
    project_dir = tmp_path

    components_pool = ComponentsConfigsPool()
    components_pool["base_component"] = ComponentConfig(name="base_component", sources=["base.c"])

    variant = VariantConfig(name="test_variant", components=["base_component"])

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components_configs_pool = components_pool

    assert project_slurper._collect_selected_component_names(variant, "test_platform") == ["base_component"]


def test_collect_selected_component_names_with_platform_config_components(tmp_path: Path) -> None:
    project_dir = tmp_path

    components_pool = ComponentsConfigsPool()
    components_pool["base_component"] = ComponentConfig(name="base_component", sources=["base.c"])
    components_pool["platform_specific_component"] = ComponentConfig(name="platform_specific_component", sources=["platform_specific.c"])

    variant = VariantConfig(name="test_variant", components=["base_component"])
    platform_config = PlatformConfig(name="test_platform", components=["platform_specific_component"])

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components_configs_pool = components_pool
    project_slurper.platforms = [platform_config]

    names_with_platform = project_slurper._collect_selected_component_names(variant, "test_platform")
    assert "base_component" in names_with_platform
    assert "platform_specific_component" in names_with_platform
    assert len(names_with_platform) == 2

    assert project_slurper._collect_selected_component_names(variant, None) == ["base_component"]


def test_collect_selected_component_names_with_both_variant_and_platform_config_components(tmp_path: Path) -> None:
    project_dir = tmp_path

    components_pool = ComponentsConfigsPool()
    components_pool["base_component"] = ComponentConfig(name="base_component", sources=["base.c"])
    components_pool["variant_platform_component"] = ComponentConfig(name="variant_platform_component", sources=["variant_platform.c"])
    components_pool["platform_config_component"] = ComponentConfig(name="platform_config_component", sources=["platform_config.c"])

    variant = VariantConfig(
        name="test_variant",
        components=["base_component"],
        platforms={"test_platform": VariantPlatformsConfig(components=["variant_platform_component"])},
    )
    platform_config = PlatformConfig(name="test_platform", components=["platform_config_component"])

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components_configs_pool = components_pool
    project_slurper.platforms = [platform_config]

    names_with_platform = project_slurper._collect_selected_component_names(variant, "test_platform")
    assert "base_component" in names_with_platform
    assert "variant_platform_component" in names_with_platform
    assert "platform_config_component" in names_with_platform
    assert len(names_with_platform) == 3
