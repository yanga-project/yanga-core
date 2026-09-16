from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.commands.features import FeaturesCommand, FeaturesCommandConfig
from yanga_core.commands.run import RunCommand
from yanga_core.domain.execution_context import UserRequestTarget
from yanga_core.domain.project_slurper import YangaProjectSlurper

PIPELINE = [{"step": "KConfigEdit", "run": "echo edit"}]
PROJECT_MODEL = {"file": "KConfig", "pipeline": PIPELINE}
PLATFORM_MODEL = {"file": "Kconfig.zephyr", "pipeline": PIPELINE}


def write_project(project_dir: Path, project_model: dict[str, Any] | None, platform_model: dict[str, Any] | None) -> YangaProjectSlurper:
    (project_dir / "KConfig").touch()
    (project_dir / "Kconfig.zephyr").touch()
    zephyr: dict[str, Any] = {"name": "zephyr", "feature_model": platform_model} if platform_model else {"name": "zephyr"}
    config: dict[str, Any] = {"variants": [{"name": "Disco"}], "platforms": [zephyr, {"name": "gtest"}]}
    if project_model:
        config["feature_model"] = project_model
    (project_dir / "yanga.yaml").write_text(yaml.safe_dump(config))
    return YangaProjectSlurper(project_dir, create_yanga_build_dir=False)


@pytest.mark.parametrize(("platform_name", "expected_file"), [(None, "KConfig"), ("zephyr", "Kconfig.zephyr")])
def test_platform_selects_the_platform_model_else_the_product_model(tmp_path: Path, platform_name: str | None, expected_file: str) -> None:
    slurper = write_project(tmp_path, PROJECT_MODEL, PLATFORM_MODEL)

    assert FeaturesCommand.select_feature_model(slurper, platform_name).file == str(tmp_path / expected_file)


@pytest.mark.parametrize(
    ("project_model", "platform_model", "platform_name", "message"),
    [
        (PROJECT_MODEL, None, "gtest", "Platform 'gtest' declares no 'feature_model:' block"),
        (None, PLATFORM_MODEL, None, "The project declares no 'feature_model:' block"),
        ({"file": "KConfig"}, None, None, "The project 'feature_model:' .*KConfig.* declares no 'pipeline:'"),
        (PROJECT_MODEL, {"file": "Kconfig.zephyr"}, "zephyr", "The 'feature_model:' of platform 'zephyr' .*Kconfig.zephyr.* declares no 'pipeline:'"),
    ],
    ids=["platform-without-model", "project-without-model", "project-model-without-pipeline", "platform-model-without-pipeline"],
)
def test_select_feature_model_errors(tmp_path: Path, project_model: dict[str, Any] | None, platform_model: dict[str, Any] | None, platform_name: str | None, message: str) -> None:
    slurper = write_project(tmp_path, project_model, platform_model)

    with pytest.raises(UserNotificationException, match=message):
        FeaturesCommand.select_feature_model(slurper, platform_name)


def test_a_platform_without_a_variant_is_an_error(tmp_path: Path) -> None:
    write_project(tmp_path, PROJECT_MODEL, PLATFORM_MODEL)

    with pytest.raises(UserNotificationException, match="Platform 'zephyr' needs --variant"):
        FeaturesCommand().do_run(FeaturesCommandConfig(project_dir=tmp_path, platform="zephyr"))


def test_do_run_runs_the_model_pipeline_with_a_features_request(tmp_path: Path) -> None:
    write_project(tmp_path, PROJECT_MODEL, PLATFORM_MODEL)

    with patch.object(RunCommand, "execute_pipeline_steps") as execute:
        FeaturesCommand().do_run(FeaturesCommandConfig(project_dir=tmp_path, variant_name="Disco", platform="zephyr", gui=False))

    kwargs = execute.call_args.kwargs
    assert [step.step for step in kwargs["pipeline"]] == ["KConfigEdit"]
    assert kwargs["platform_name"] == "zephyr"
    request = kwargs["user_request"]
    assert (request.variant_name, request.platform_name, request.target, request.extra) == ("Disco", "zephyr", UserRequestTarget.FEATURES, {"gui": False})
