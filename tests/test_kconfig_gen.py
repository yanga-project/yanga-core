from pathlib import Path
from unittest.mock import Mock

import pytest
from py_app_dev.core.data_registry import DataRegistry

from yanga_core.domain.execution_context import ExecutionContext
from yanga_core.domain.reports import ReportRelevantFiles
from yanga_core.steps.kconfig_gen import KConfigGen


@pytest.fixture
def execution_context(tmp_path: Path) -> ExecutionContext:
    ctx = Mock(spec=ExecutionContext)
    ctx.project_root_dir = tmp_path
    ctx.spl_paths = Mock()
    ctx.spl_paths.variant_build_dir = tmp_path / "build"
    return ctx


@pytest.mark.parametrize(
    "config, expected_filename",
    [
        (None, "KConfig"),
        ({}, "KConfig"),
        ({"kconfig_model_file": "my/custom/KConfig"}, "my/custom/KConfig"),
    ],
    ids=["no-config", "empty-config", "custom-path"],
)
def test_kconfig_model_file(
    execution_context: ExecutionContext,
    config: dict[str, str] | None,
    expected_filename: str,
) -> None:
    step = KConfigGen(execution_context, config=config)
    assert step.kconfig_model_file == execution_context.project_root_dir / expected_filename


@pytest.mark.parametrize(
    "config, expected_stem",
    [
        (None, "autoconf"),
        ({"output_stem": "product_features"}, "product_features"),
    ],
    ids=["default-stem", "custom-stem"],
)
def test_output_stem(
    execution_context: ExecutionContext,
    config: dict[str, str] | None,
    expected_stem: str,
) -> None:
    step = KConfigGen(execution_context, config=config)
    kconfig_dir = execution_context.spl_paths.variant_build_dir / "kconfig"
    assert step.get_outputs() == [kconfig_dir / f"{expected_stem}.{ext}" for ext in ("h", "md", "json")]
    assert step.json_config_file == kconfig_dir / f"{expected_stem}.json"


def test_features_documentation_is_tagged_as_variant_configuration(execution_context: ExecutionContext) -> None:
    (execution_context.project_root_dir / "KConfig").write_text('config FOO\n    bool "Foo"\n    default y\n')
    execution_context.configure_mock(data_registry=DataRegistry(), variant_feature_selection_file=None)

    assert KConfigGen(execution_context).run() == 0

    assert [entry.tags for entry in execution_context.data_registry.find_data(ReportRelevantFiles)] == [["variant", "configuration"]]
