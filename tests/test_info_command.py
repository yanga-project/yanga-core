import shutil
from argparse import ArgumentParser
from pathlib import Path
from textwrap import dedent

import pytest

from tests.utils import write_file
from yanga_core.commands.info import InfoCommand, InfoCommandConfig
from yanga_core.commands.info_schema import SCHEMA_VERSION, InfoProject
from yanga_core.domain.config import BuildTargets
from yanga_core.domain.project_slurper import DEFAULT_EXCLUDE_DIRS

INFO_COMMAND_FIXTURE_DIR = Path(__file__).parent / "data" / "info_command"
PROJECT_DIR_PLACEHOLDER = "<PROJECT_DIR>"


def _yanga_yaml(content: str) -> str:
    return dedent(content).lstrip()


def _make_minimal_project(root: Path) -> None:
    write_file(
        root / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: Default
                components: [app, common]
            platforms:
              - name: gtest
                build_types: [Debug, Release]
                build_targets: [unit_tests]
                components: [mock_lib]
            components:
              - name: app
                path: src/app
              - name: common
                path: src/common
              - name: mock_lib
                path: src/platforms/gtest/mock_lib
        """),
    )


def _run_and_parse(project_dir: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, InfoProject, str]:
    """Run InfoCommand to stdout and parse the result back through the dataclass."""
    exit_code = InfoCommand().do_run(InfoCommandConfig(project_dir=project_dir))
    payload = capsys.readouterr().out
    return exit_code, InfoProject.from_json(payload), payload


def test_clean_project_schema(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _make_minimal_project(tmp_path)

    exit_code, info, payload = _run_and_parse(tmp_path, capsys)

    assert exit_code == 0
    assert payload.endswith("\n")
    assert info.schema_version == SCHEMA_VERSION
    assert info.project_dir == str(tmp_path.resolve())

    assert info.watch_patterns == ["**/yanga.yaml"]
    assert "yanga.yaml" in info.config_files

    assert [p.name for p in info.platforms] == ["gtest"]
    gtest = info.platforms[0]
    assert gtest.build_types == ["Debug", "Release"]
    # Bare-list config form normalizes to generic on the wire.
    assert gtest.build_targets == BuildTargets(generic=["unit_tests"])
    assert gtest.components == ["mock_lib"]

    assert len(info.variants) == 1
    variant = info.variants[0]
    assert variant.name == "Default"
    assert variant.components == ["app", "common"]
    assert variant.platform_components == {}

    by_name = {c.name: c for c in info.components}
    assert by_name["app"].path == "src/app"
    assert by_name["common"].path == "src/common"
    assert by_name["mock_lib"].path == "src/platforms/gtest/mock_lib"

    assert info.diagnostics == []


def test_build_targets_split_form_preserves_structure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The dataclass form is preserved verbatim on the wire."""
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: V
                components: [a]
            platforms:
              - name: host
                build_targets:
                  generic: [all]
                  variant: [docs]
                  component: [unit_tests]
            components:
              - name: a
        """),
    )

    _, info, _ = _run_and_parse(tmp_path, capsys)

    host = info.platforms[0]
    assert host.build_targets == BuildTargets(generic=["all"], variant=["docs"], component=["unit_tests"])


def test_build_targets_component_only_preserves_empty_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """All three keys are always present in the wire dict, even when unset in the config."""
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: V
                components: [a]
            platforms:
              - name: host
                build_targets:
                  component: [unit_tests, coverage]
            components:
              - name: a
        """),
    )

    _, info, payload = _run_and_parse(tmp_path, capsys)

    host = info.platforms[0]
    assert host.build_targets == BuildTargets(component=["unit_tests", "coverage"])
    # All three keys are always emitted; the extension can rely on a stable shape.
    assert '"generic": []' in payload
    assert '"variant": []' in payload


def test_get_effective_variant_components_merges_three_sources(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: V
                components: [app, common]
                platforms:
                  host:
                    components: [host_helpers]
            platforms:
              - name: host
                components: [mock_lib]
            components:
              - name: app
              - name: common
              - name: host_helpers
              - name: mock_lib
        """),
    )

    _, info, _ = _run_and_parse(tmp_path, capsys)

    assert info.get_effective_variant_components("V", "host") == ["app", "common", "host_helpers", "mock_lib"]


def test_get_effective_variant_components_dedupes_overlap(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: V
                components: [app, shared]
                platforms:
                  host:
                    components: [shared, helpers]
            platforms:
              - name: host
                components: [helpers, mock_lib]
            components:
              - name: app
              - name: shared
              - name: helpers
              - name: mock_lib
        """),
    )

    _, info, _ = _run_and_parse(tmp_path, capsys)

    assert info.get_effective_variant_components("V", "host") == ["app", "shared", "helpers", "mock_lib"]


def test_get_effective_variant_components_unknown_variant_returns_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _make_minimal_project(tmp_path)
    _, info, _ = _run_and_parse(tmp_path, capsys)
    assert info.get_effective_variant_components("DoesNotExist", "gtest") == []


def test_three_source_component_union(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: Disco
                components: [app, common]
                platforms:
                  gtest:
                    components: [disco_test_helpers]
                  arduino:
                    components: [disco_arduino_glue]
            platforms:
              - name: gtest
                components: [mock_lib]
              - name: arduino
                components: [arduino_hal]
            components:
              - name: app
              - name: common
              - name: mock_lib
              - name: arduino_hal
              - name: disco_test_helpers
              - name: disco_arduino_glue
        """),
    )

    _, info, _ = _run_and_parse(tmp_path, capsys)

    variant = info.variants[0]
    assert variant.components == ["app", "common"]
    assert variant.platform_components == {
        "gtest": ["disco_test_helpers"],
        "arduino": ["disco_arduino_glue"],
    }
    platforms_by_name = {p.name: p for p in info.platforms}
    assert platforms_by_name["gtest"].components == ["mock_lib"]
    assert platforms_by_name["arduino"].components == ["arduino_hal"]
    assert {c.name for c in info.components} == {
        "app",
        "common",
        "mock_lib",
        "arduino_hal",
        "disco_test_helpers",
        "disco_arduino_glue",
    }
    assert info.diagnostics == []


def test_config_files_includes_yanga_ini_and_pyproject(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _make_minimal_project(tmp_path)
    write_file(tmp_path / "yanga.ini", "[yanga]\n")
    write_file(tmp_path / "pyproject.toml", '[tool.yanga]\nconfiguration_file_name = "yanga.yaml"\n')
    write_file(
        tmp_path / "src/components/extra/yanga.yaml",
        _yanga_yaml("""
            components:
              - name: extra
                path: src/components/extra
        """),
    )

    _, info, _ = _run_and_parse(tmp_path, capsys)

    assert "yanga.ini" in info.config_files
    assert "pyproject.toml" in info.config_files
    assert "yanga.yaml" in info.config_files
    assert "src/components/extra/yanga.yaml" in info.config_files
    assert len(info.config_files) == len(set(info.config_files))


def test_watch_patterns_respects_custom_configuration_file_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_file(tmp_path / "yanga.ini", "[yanga]\nconfiguration_file_name = my_yanga.yaml\n")
    write_file(
        tmp_path / "my_yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: V
                components: [a]
            components:
              - name: a
        """),
    )

    _, info, _ = _run_and_parse(tmp_path, capsys)

    assert info.watch_patterns == ["**/my_yanga.yaml"]


def test_ignore_patterns_merges_defaults_and_user_excludes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _make_minimal_project(tmp_path)
    write_file(tmp_path / "yanga.ini", "[yanga]\nexclude_dirs = node_modules, dist\n")

    _, info, _ = _run_and_parse(tmp_path, capsys)

    expected = sorted({*DEFAULT_EXCLUDE_DIRS, "node_modules", "dist"})
    assert info.ignore_patterns == [f"{d}/**" for d in expected]


def test_output_file_matches_stdout_bytes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _make_minimal_project(tmp_path)

    InfoCommand().do_run(InfoCommandConfig(project_dir=tmp_path))
    stdout_bytes = capsys.readouterr().out

    output_file = tmp_path / "out" / "project.json"
    InfoCommand().do_run(InfoCommandConfig(project_dir=tmp_path, output=output_file))
    file_bytes = output_file.read_text()

    assert stdout_bytes == file_bytes
    assert capsys.readouterr().out == ""


def test_unknown_component_in_variant_yields_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: Broken
                components: [app, missing_component]
            components:
              - name: app
        """),
    )

    exit_code, info, _ = _run_and_parse(tmp_path, capsys)

    # Per D3: warnings do not flip the exit code; only `error` severity does.
    assert exit_code == 0
    warnings = [d for d in info.diagnostics if d.severity == "warning"]
    assert any(d.code == "yanga.unknown_component" and "missing_component" in d.message for d in warnings)
    assert info.variants[0].name == "Broken"
    assert info.variants[0].components == ["app", "missing_component"]


def test_unknown_platform_overlay_yields_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: V
                components: [app]
                platforms:
                  not_a_real_platform:
                    components: [app]
            components:
              - name: app
        """),
    )

    _, info, _ = _run_and_parse(tmp_path, capsys)

    assert any(d.code == "yanga.unknown_platform_overlay" for d in info.diagnostics)


def test_diagnostic_optional_fields_are_omitted_when_none(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_file(
        tmp_path / "yanga.yaml",
        _yanga_yaml("""
            variants:
              - name: V
                components: [missing]
            components:
              - name: app
        """),
    )

    _, _, payload = _run_and_parse(tmp_path, capsys)

    # mashumaro's omit_none should keep `line` and `column` out of the JSON entirely.
    assert '"line"' not in payload
    assert '"column"' not in payload


def test_integration_against_fixture_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """End-to-end: copy a checked-in yanga.yaml into a tmp project, run InfoCommand, compare to a checked-in yanga_info.json."""
    shutil.copy(INFO_COMMAND_FIXTURE_DIR / "yanga.yaml", tmp_path / "yanga.yaml")

    exit_code = InfoCommand().do_run(InfoCommandConfig(project_dir=tmp_path))
    payload = capsys.readouterr().out

    assert exit_code == 0

    actual = InfoProject.from_json(payload)
    expected = InfoProject.from_json_file(INFO_COMMAND_FIXTURE_DIR / "yanga_info.json")
    expected.project_dir = str(tmp_path.resolve())

    assert actual == expected


def test_register_arguments_exposes_output_flag(tmp_path: Path) -> None:
    parser = ArgumentParser()
    InfoCommand()._register_arguments(parser)
    namespace = parser.parse_args(["--project-dir", str(tmp_path), "--output", str(tmp_path / "out.json")])
    assert namespace.output == tmp_path / "out.json"
    assert namespace.project_dir == tmp_path
