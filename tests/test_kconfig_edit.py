import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.domain.config import FeatureModelConfig, FeatureSelectionConfig, PlatformConfig, VariantConfig, VariantPlatformsConfig
from yanga_core.domain.execution_context import ExecutionContext, UserRequest, UserRequestScope, UserRequestTarget
from yanga_core.domain.spl_paths import SPLPaths
from yanga_core.steps.kconfig_edit import KConfigEdit, KConfigEditScope


def make_context(tmp_path: Path, variant: bool = True, platform: bool = False, extra: dict[str, bool] | None = None) -> ExecutionContext:
    for relative in (
        "KConfig",
        "platforms/zephyr/yanga.yaml",
        "platforms/zephyr/Kconfig",
        "platforms/zephyr/prj.conf",
        "variants/Disco/yanga.yaml",
        "variants/Disco/config.txt",
        "variants/Disco/zephyr.txt",
    ):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).touch()
    context = Mock(spec=ExecutionContext)
    # The real lookups, on the mock's own class, so they read the variant, platform and paths set below.
    type(context).variant_feature_selection_file = ExecutionContext.variant_feature_selection_file
    type(context).variant_platform_feature_selection_file = ExecutionContext.variant_platform_feature_selection_file
    context.project_root_dir = tmp_path
    context.feature_model = FeatureModelConfig(file=str(tmp_path / "KConfig"))
    context.platform = PlatformConfig(
        name="zephyr",
        feature_model=FeatureModelConfig(file=str(tmp_path / "platforms/zephyr/Kconfig")),
        feature_selection=FeatureSelectionConfig(file="prj.conf"),
        file=tmp_path / "platforms/zephyr/yanga.yaml",
    )
    context.variant = (
        VariantConfig(
            name="Disco",
            feature_selection=FeatureSelectionConfig(file="config.txt"),
            platforms={"zephyr": VariantPlatformsConfig(feature_selection=FeatureSelectionConfig(file="zephyr.txt"))},
            file=tmp_path / "variants/Disco/yanga.yaml",
        )
        if variant
        else None
    )
    context.spl_paths = SPLPaths(tmp_path, "Disco", "zephyr" if platform else None, None, create_yanga_build_dir=False)
    context.user_request = UserRequest(
        UserRequestScope.VARIANT,
        variant_name="Disco" if variant else None,
        platform_name="zephyr" if platform else None,
        target=UserRequestTarget.FEATURES,
        extra=extra or {},
    )
    context.create_process_env.return_value = {"SRCTREE": "/zephyr"}
    return context


@pytest.mark.parametrize(
    ("platform", "model", "selection"),
    [
        (False, "KConfig", "variants/Disco/config.txt"),
        (True, "platforms/zephyr/Kconfig", "variants/Disco/zephyr.txt"),
    ],
    ids=["variant", "variant-and-platform"],
)
def test_scope_follows_the_request(tmp_path: Path, platform: bool, model: str, selection: str) -> None:
    context = make_context(tmp_path, variant=True, platform=platform)

    scope = KConfigEdit(context).scope

    assert scope == KConfigEditScope(tmp_path / model, tmp_path / selection)


@pytest.mark.parametrize(
    ("variant", "platform", "remove", "message"),
    [
        (True, False, lambda c: setattr(c, "feature_model", None), "The project declares no 'feature_model:' block"),
        (False, False, lambda c: None, "Select a variant"),
        (True, False, lambda c: setattr(c.variant, "feature_selection", None), "Variant 'Disco' has no 'feature_selection:' configured"),
        (True, True, lambda c: setattr(c.platform, "feature_model", None), "Platform 'zephyr' declares no 'feature_model:' block"),
        (True, True, lambda c: setattr(c.variant, "platforms", None), "Variant 'Disco' has no 'feature_selection:' configured for platform 'zephyr'"),
    ],
    ids=["no-product-model", "no-variant", "no-variant-selection", "no-platform-model", "no-variant-platform-selection"],
)
def test_scope_requires_the_declarations(tmp_path: Path, variant: bool, platform: bool, remove: Callable[[Mock], None], message: str) -> None:
    context = make_context(tmp_path, variant, platform)
    remove(context)

    with pytest.raises(UserNotificationException, match=message):
        _ = KConfigEdit(context).scope


@pytest.mark.parametrize(
    ("extra", "editor"),
    [({}, "guiconfig"), ({"gui": False}, "menuconfig")],
    ids=["default-gui", "no-gui"],
)
def test_command_runs_the_kconfiglib_editor_on_the_model(tmp_path: Path, extra: dict[str, bool], editor: str) -> None:
    step = KConfigEdit(make_context(tmp_path, variant=True, extra=extra))
    scope = step.scope

    assert step.create_command(scope) == [sys.executable, "-m", editor, str(scope.model_file)]


@pytest.mark.parametrize("returncode", [0, 1])
def test_run_points_the_editor_at_the_selection_file_and_fails_on_editor_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(_command: list[str], **kwargs: object) -> Mock:
        calls.append(kwargs)
        return Mock(returncode=returncode)

    monkeypatch.setattr("yanga_core.steps.kconfig_edit.subprocess.run", fake_run)
    step = KConfigEdit(make_context(tmp_path))

    if returncode:
        with pytest.raises(UserNotificationException, match="exited with code 1"):
            step.run()
    else:
        assert step.run() == 0
    assert calls[0]["env"] == {"SRCTREE": "/zephyr", "KCONFIG_CONFIG": str(tmp_path / "variants/Disco/config.txt")}
    assert calls[0]["cwd"] == tmp_path


def test_overview_without_variant_and_platform_opens_the_viewer(tmp_path: Path) -> None:
    step = KConfigEdit(make_context(tmp_path, variant=False, platform=False))

    assert step.is_overview
    assert step.create_overview_command() == [sys.executable, "-m", "yanga_core.commands", "kconfig_view", "--project-dir", str(tmp_path)]


@pytest.mark.parametrize(
    ("remove", "extra", "message"),
    [
        (lambda c: setattr(c, "feature_model", None), {}, "The project declares no 'feature_model:' block"),
        (lambda c: None, {"gui": False}, "no terminal view"),
    ],
    ids=["no-product-model", "no-gui"],
)
def test_overview_errors(tmp_path: Path, remove: Callable[[Mock], None], extra: dict[str, bool], message: str) -> None:
    context = make_context(tmp_path, variant=False, platform=False, extra=extra)
    remove(context)

    with pytest.raises(UserNotificationException, match=message):
        KConfigEdit(context).create_overview_command()
