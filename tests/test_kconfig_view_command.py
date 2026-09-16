from pathlib import Path
from typing import Any

import pytest
import yaml
from kspl.kconfig import TriState
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.commands.kconfig_view import ProductFeaturesData

MODEL = 'config LANG_DE\n    bool "German"\n\nconfig DEBUG_MODE\n    bool "Debug"\n    default y\n'


def write_project(project_dir: Path, config: dict[str, Any]) -> None:
    (project_dir / "KConfig").write_text(MODEL)
    (project_dir / "variants" / "German").mkdir(parents=True)
    (project_dir / "variants" / "German" / "config.txt").write_text("CONFIG_LANG_DE=y\nCONFIG_DEBUG_MODE=n\n")
    (project_dir / "yanga.yaml").write_text(yaml.safe_dump(config))


def test_each_variant_shows_its_declared_selection(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        {
            "feature_model": {"file": "KConfig"},
            "variants": [{"name": "English"}, {"name": "German", "feature_selection": {"file": "variants/German/config.txt"}}],
        },
    )

    data = ProductFeaturesData(tmp_path)

    assert [element.name for element in data.get_elements()] == ["LANG_DE", "DEBUG_MODE"]
    assert {variant.name: variant.config_dict for variant in data.get_variants()} == {
        "English": {"LANG_DE": TriState.N, "DEBUG_MODE": TriState.Y},
        "German": {"LANG_DE": TriState.Y, "DEBUG_MODE": TriState.N},
    }
    assert data.find_variant_config("German") is not None
    assert data.find_variant_config("Missing") is None


def test_no_variants_shows_the_model_defaults(tmp_path: Path) -> None:
    write_project(tmp_path, {"feature_model": {"file": "KConfig"}})

    assert [variant.name for variant in ProductFeaturesData(tmp_path).get_variants()] == ["Default"]


def test_requires_the_product_feature_model(tmp_path: Path) -> None:
    write_project(tmp_path, {"variants": [{"name": "English"}]})

    with pytest.raises(UserNotificationException, match="The project declares no 'feature_model:' block"):
        ProductFeaturesData(tmp_path)
