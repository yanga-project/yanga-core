from pathlib import Path
from unittest.mock import patch

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.commands.run import RunCommand, RunCommandConfig
from yanga_core.ini import YangaIni


def run_pristine(config: RunCommandConfig) -> None:
    ini = YangaIni.from_toml_or_ini(config.project_dir / "yanga.ini", config.project_dir / "pyproject.toml")
    RunCommand._run_pristine(config, ini)


@pytest.fixture
def populated_project(tmp_path: Path) -> Path:
    build_dir = tmp_path / ".yanga" / "build" / "variants" / "MyVariant" / "host" / "Debug"
    build_dir.mkdir(parents=True)
    (build_dir / "stale.txt").write_text("")
    return tmp_path


def test_pristine_wipes_targeted_variant_build_dir(populated_project: Path) -> None:
    target = populated_project / ".yanga" / "build" / "variants" / "MyVariant" / "host" / "Debug"

    run_pristine(RunCommandConfig(project_dir=populated_project, pristine=True, variant_name="MyVariant", platform="host", build_type="Debug"))

    assert not target.exists()
    assert (populated_project / ".yanga" / "build" / "variants" / "MyVariant" / "host").exists()


def test_pristine_with_no_scope_wipes_entire_yanga_build(populated_project: Path) -> None:
    run_pristine(RunCommandConfig(project_dir=populated_project, pristine=True))

    assert not (populated_project / ".yanga" / "build").exists()


def test_pristine_is_a_no_op_if_target_does_not_exist(tmp_path: Path) -> None:
    run_pristine(RunCommandConfig(project_dir=tmp_path, pristine=True, variant_name="Ghost"))


@pytest.mark.parametrize("bad_variant", ["..", "/etc"])
def test_pristine_refuses_to_escape_build_root(bad_variant: str, tmp_path: Path) -> None:
    with pytest.raises(UserNotificationException, match="escapes yanga build root"):
        run_pristine(RunCommandConfig(project_dir=tmp_path, pristine=True, variant_name=bad_variant))


def test_pristine_wraps_oserror_into_user_notification(populated_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr("yanga_core.commands.run.shutil.rmtree", explode)

    with pytest.raises(UserNotificationException, match="Failed to wipe"):
        run_pristine(RunCommandConfig(project_dir=populated_project, pristine=True, variant_name="MyVariant", platform="host", build_type="Debug"))


def test_do_run_invokes_pristine_before_creating_slurper(populated_project: Path) -> None:
    target = populated_project / ".yanga" / "build" / "variants" / "MyVariant" / "host" / "Debug"

    with patch.object(RunCommand, "create_project_slurper", side_effect=RuntimeError("slurper stop")):
        with pytest.raises(RuntimeError, match="slurper stop"):
            RunCommand().do_run(RunCommandConfig(project_dir=populated_project, pristine=True, variant_name="MyVariant", platform="host", build_type="Debug"))

    assert not target.exists()


def test_do_run_does_not_wipe_when_pristine_false(populated_project: Path) -> None:
    target = populated_project / ".yanga" / "build" / "variants" / "MyVariant" / "host" / "Debug"

    with patch.object(RunCommand, "create_project_slurper", side_effect=RuntimeError("slurper stop")):
        with pytest.raises(RuntimeError):
            RunCommand().do_run(RunCommandConfig(project_dir=populated_project, pristine=False, variant_name="MyVariant"))

    assert target.exists()
