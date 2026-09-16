from pathlib import Path
from unittest.mock import Mock

import pytest

from yanga_core.domain.config import FeatureSelectionConfig, VariantConfig
from yanga_core.domain.execution_context import ExecutionContext
from yanga_core.domain.spl_paths import SPLPaths
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


def test_features_selection_file_is_the_variants_product_selection(tmp_path: Path) -> None:
    variant_dir = tmp_path / "variants" / "Disco"
    variant_dir.mkdir(parents=True)
    (variant_dir / "config.txt").touch()
    context = Mock(spec=ExecutionContext)
    context.project_root_dir = tmp_path
    context.spl_paths = SPLPaths(tmp_path, "Disco", None, None, create_yanga_build_dir=False)
    context.variant = VariantConfig(name="Disco", feature_selection=FeatureSelectionConfig(file="config.txt"), file=variant_dir / "yanga.yaml")

    assert KConfigGen(context).features_selection_file == variant_dir / "config.txt"

    context.variant = VariantConfig(name="Sleep")
    assert KConfigGen(context).features_selection_file is None
