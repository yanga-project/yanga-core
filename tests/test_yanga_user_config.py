import textwrap
from pathlib import Path

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.domain.config import YangaUserConfig


def test_load_pipeline_from_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
    pipeline:
        install:
            - step: ScoopInstall
              module: yanga_core.steps.scoop_install
            - step: MyInstall
              file: user/install.py
              class: CustomInstall
        build:
            - step: MyPreBuild
              file: user/build.py
              class: CustomPreBuild
            - step: ExecuteBuild
              module: yanga.cmake.steps
            - step: MyPostBuild
              file: user/build.py
              class: CustomPostBuild
        deploy:
            - step: YangaDeploy
    """
        )
    )
    config = YangaUserConfig.from_file(config_file)
    assert config.pipeline and isinstance(config.pipeline, dict)
    assert config.pipeline["install"][0].step == "ScoopInstall"
    assert config.pipeline["install"][1].step == "MyInstall"
    assert config.file == config_file, "file name should be automatically added to config"


def test_load_user_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
    components:
      - name: main
        type: component
        sources:
          - main.c

    variants:
      - name: EnglishVariant
        description: Say hello in English.
        components:
          - main
      - name: GermanVariant
        description: Say hello in German.
        components:
          - main
        feature_selection:
          file: "config_de.txt"

    pipeline:
      install:
        - step: ScoopInstall
          module: yanga_core.steps.scoop_install
          description: Install dependencies
          timeout_sec: 120
      gen:
        - step: KConfigGen
          module: yanga_core.steps.kconfig_gen
      build:
        - step: GenerateBuildSystemFiles
          module: yanga.cmake.steps
        - step: ExecuteBuild
          module: yanga.cmake.steps

    """
        )
    )
    config = YangaUserConfig.from_file(config_file)
    assert config.variants
    de_variant = next((v for v in config.variants if v.name == "GermanVariant"), None)
    assert de_variant
    assert de_variant.feature_selection
    assert de_variant.feature_selection.file == "config_de.txt"
    en_variant = next((v for v in config.variants if v.name == "EnglishVariant"), None)
    assert en_variant
    assert en_variant.feature_selection is None


def test_feature_model_and_selection_blocks(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
    feature_model:
      description: Product features
      file: KConfig
      pipeline:
        - step: KConfigEdit
          module: yanga_core.steps.kconfig_edit
    platforms:
      - name: zephyr
        feature_model:
          file: zephyr/Kconfig
        feature_selection:
          file: platforms/zephyr/prj.conf
    variants:
      - name: Disco
        components: [main]
        feature_selection:
          description: Disco features
          file: config.txt
        platforms:
          zephyr:
            feature_selection:
              file: variants/Disco/zephyr.conf
    """
        )
    )
    config = YangaUserConfig.from_file(config_file)
    assert config.feature_model
    assert (config.feature_model.file, config.feature_model.description) == ("KConfig", "Product features")
    assert [step.step for step in config.feature_model.pipeline or []] == ["KConfigEdit"]
    assert config.platforms[0].feature_model and config.platforms[0].feature_model.file == "zephyr/Kconfig"
    assert config.platforms[0].feature_selection and config.platforms[0].feature_selection.file == "platforms/zephyr/prj.conf"
    variant = config.variants[0]
    assert variant.feature_selection and variant.feature_selection.file == "config.txt"
    assert variant.platforms and variant.platforms["zephyr"].feature_selection
    assert variant.platforms["zephyr"].feature_selection.file == "variants/Disco/zephyr.conf"


def test_removed_features_selection_file_key_is_an_error(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        textwrap.dedent(
            """\
    variants:
      - name: Disco
        components: [main]
        features_selection_file: config.txt
    """
        )
    )
    with pytest.raises(UserNotificationException, match=r"'Disco'.*feature_selection"):
        YangaUserConfig.from_file(config_file)
