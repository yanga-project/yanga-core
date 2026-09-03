import textwrap
from pathlib import Path

import pytest
from py_app_dev.core.exceptions import UserNotificationException
from pypeline.domain.pipeline import PipelineStepConfig

from yanga_core.commands.run import RunCommand
from yanga_core.domain.config import ComponentConfig, PlatformConfig, VariantConfig, VariantPlatformsConfig
from yanga_core.domain.execution_context import UserRequest, UserRequestScope
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

    assert [step.step for step in project_slurper.project_pipeline or []] == ["CreateVEnv", "Build"]


@pytest.mark.parametrize(
    ("platform_name", "expected_steps"),
    [
        ("zephyr", ["ZephyrBuild"]),
        ("gtest", ["Build"]),
        (None, ["Build"]),
    ],
)
def test_get_pipeline_prefers_the_platform_pipeline(tmp_path: Path, platform_name: str | None, expected_steps: list[str]) -> None:
    """
    A platform that builds differently from the rest of the project declares its own pipeline.

    It replaces the project one for that platform::

        platforms:
          - name: zephyr
            pipeline:
              - include: pipeline/bootstrap.yaml
              - step: ZephyrBuild
                module: my_project.steps

    Platforms without one, and runs without a platform, use the project pipeline.
    """
    project_slurper = YangaProjectSlurper(project_dir=tmp_path, create_yanga_build_dir=False)
    project_slurper.project_pipeline = [PipelineStepConfig(step="Build")]
    project_slurper.platforms = [PlatformConfig(name="zephyr", pipeline=[PipelineStepConfig(step="ZephyrBuild")]), PlatformConfig(name="gtest")]

    assert [step.step for step in project_slurper.get_pipeline(platform_name) or []] == expected_steps


def test_platform_pipeline_include_resolves_against_the_project_root(tmp_path: Path) -> None:
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "bootstrap.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - step: CreateVEnv
                  run: echo "venv"
            """)
    )
    platform_dir = tmp_path / "platforms" / "zephyr"
    platform_dir.mkdir(parents=True)
    (platform_dir / "yanga.yaml").write_text(
        textwrap.dedent("""\
            platforms:
                - name: zephyr
                  pipeline:
                    - include: pipeline/bootstrap.yaml
                    - step: ZephyrBuild
                      run: echo "build"
            """)
    )

    project_slurper = YangaProjectSlurper(project_dir=tmp_path, create_yanga_build_dir=False)

    assert [step.step for step in project_slurper.get_pipeline("zephyr") or []] == ["CreateVEnv", "ZephyrBuild"]


def test_run_without_any_pipeline_fails_for_a_selected_platform(tmp_path: Path) -> None:
    project_slurper = YangaProjectSlurper(project_dir=tmp_path, create_yanga_build_dir=False)
    project_slurper.platforms = [PlatformConfig(name="zephyr")]

    with pytest.raises(UserNotificationException, match="No pipeline found"):
        RunCommand.execute_pipeline_steps(tmp_path, project_slurper, UserRequest(scope=UserRequestScope.VARIANT), platform_name="zephyr")


def test_two_top_level_pipelines_is_an_error(tmp_path: Path) -> None:
    """
    Exactly one ``yanga.yaml`` may declare the top-level ``pipeline:``.

    A platform pipeline goes under the ``platforms:`` entry. A top-level one in
    ``platforms/<name>/yanga.yaml`` is a second project pipeline, and the files are slurped in
    parallel, so silently keeping one of them is a coin toss.
    """
    (tmp_path / "yanga.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - step: Build
                  run: echo "build"
            """)
    )
    platform_dir = tmp_path / "platforms" / "zephyr"
    platform_dir.mkdir(parents=True)
    (platform_dir / "yanga.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
                - step: ZephyrBuild
                  run: echo "build"
            """)
    )

    with pytest.raises(UserNotificationException, match="defined in multiple configuration files") as error:
        YangaProjectSlurper(project_dir=tmp_path, create_yanga_build_dir=False)

    assert "platforms" in str(error.value), "the error must name both files"
