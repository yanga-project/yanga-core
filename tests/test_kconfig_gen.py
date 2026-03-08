from pathlib import Path
from unittest.mock import Mock

import pytest

from yanga_core.domain.execution_context import ExecutionContext
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
