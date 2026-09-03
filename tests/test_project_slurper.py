import textwrap
from pathlib import Path

from yanga_core.domain.config import ComponentConfig, PlatformConfig, VariantConfig, VariantPlatformsConfig
from yanga_core.domain.project_slurper import YangaProjectSlurper


def test_collect_selected_component_names_with_platform_specific(tmp_path: Path) -> None:
    project_dir = tmp_path

    variant = VariantConfig(
        name="test_variant",
        components=["base_component"],
        platforms={"test_platform": VariantPlatformsConfig(components=["platform_component"])},
    )

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components = [
        ComponentConfig(name="base_component", sources=["base.c"]),
        ComponentConfig(name="platform_component", sources=["platform.c"]),
    ]

    names_with_platform = project_slurper._collect_selected_component_names(variant, "test_platform")
    assert "base_component" in names_with_platform
    assert "platform_component" in names_with_platform
    assert len(names_with_platform) == 2

    assert project_slurper._collect_selected_component_names(variant, None) == ["base_component"]
    assert project_slurper._collect_selected_component_names(variant, "other_platform") == ["base_component"]


def test_collect_selected_component_names_no_platform_config(tmp_path: Path) -> None:
    project_dir = tmp_path

    variant = VariantConfig(name="test_variant", components=["base_component"])

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components = [ComponentConfig(name="base_component", sources=["base.c"])]

    assert project_slurper._collect_selected_component_names(variant, "test_platform") == ["base_component"]


def test_collect_selected_component_names_with_platform_config_components(tmp_path: Path) -> None:
    project_dir = tmp_path

    variant = VariantConfig(name="test_variant", components=["base_component"])
    platform_config = PlatformConfig(name="test_platform", components=["platform_specific_component"])

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components = [
        ComponentConfig(name="base_component", sources=["base.c"]),
        ComponentConfig(name="platform_specific_component", sources=["platform_specific.c"]),
    ]
    project_slurper.platforms = [platform_config]

    names_with_platform = project_slurper._collect_selected_component_names(variant, "test_platform")
    assert "base_component" in names_with_platform
    assert "platform_specific_component" in names_with_platform
    assert len(names_with_platform) == 2

    assert project_slurper._collect_selected_component_names(variant, None) == ["base_component"]


def test_collect_selected_component_names_with_both_variant_and_platform_config_components(tmp_path: Path) -> None:
    project_dir = tmp_path

    variant = VariantConfig(
        name="test_variant",
        components=["base_component"],
        platforms={"test_platform": VariantPlatformsConfig(components=["variant_platform_component"])},
    )
    platform_config = PlatformConfig(name="test_platform", components=["platform_config_component"])

    project_slurper = YangaProjectSlurper(project_dir=project_dir, create_yanga_build_dir=False)
    project_slurper.components = [
        ComponentConfig(name="base_component", sources=["base.c"]),
        ComponentConfig(name="variant_platform_component", sources=["variant_platform.c"]),
        ComponentConfig(name="platform_config_component", sources=["platform_config.c"]),
    ]
    project_slurper.platforms = [platform_config]

    names_with_platform = project_slurper._collect_selected_component_names(variant, "test_platform")
    assert "base_component" in names_with_platform
    assert "variant_platform_component" in names_with_platform
    assert "platform_config_component" in names_with_platform
    assert len(names_with_platform) == 3


def test_pipeline_include_resolves_for_a_nested_config(tmp_path: Path) -> None:
    # A fragment named relative to the project root, included from a yanga.yaml that
    # does not sit next to it: pypeline alone would look only next to the including file.
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "bootstrap.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - step: CreateVEnv
                  run: echo "venv"
            """)
    )
    variant_dir = tmp_path / "variants" / "Disco"
    variant_dir.mkdir(parents=True)
    (variant_dir / "yanga.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - include: pipeline/bootstrap.yaml
                - step: Build
                  run: echo "build"
            """)
    )

    project_slurper = YangaProjectSlurper(project_dir=tmp_path, create_yanga_build_dir=False)

    assert [step.step for step in project_slurper.pipeline or []] == ["CreateVEnv", "Build"]
