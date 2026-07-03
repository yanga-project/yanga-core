import json
from pathlib import Path
from typing import Any

import pytest

from yanga_core.docs.sphinx import SphinxConfig, SphinxReportConfig
from yanga_core.domain.execution_context import UserRequest, UserRequestScope, UserRequestTarget
from yanga_core.domain.reports import (
    ReportData,
    ReportRelevantFiles,
    ReportRelevantFileType,
    ReportRelevantHtmlContent,
    ReportScope,
    VariantReportData,
)


def _write_config(tmp_path: Path, data: dict[str, Any]) -> Path:
    config_file = tmp_path / "report_config.json"
    config_file.write_text(json.dumps(data))
    return config_file


def _variant_link(variant: str, platform: str, href: str) -> ReportRelevantFiles:
    """A per-variant report link is just a reference to generated HTML — same as a coverage report."""
    return ReportRelevantFiles(
        target=UserRequest(UserRequestScope.VARIANT, variant_name=variant, target=UserRequestTarget.NONE),
        file_type=ReportRelevantFileType.HTML,
        files_to_be_included=[],
        html_content=ReportRelevantHtmlContent(name=f"{variant} ({platform})", index_html=Path(href)),
    )


def _spl_report(project_dir: Path) -> ReportData:
    return ReportData(
        project_dir=project_dir,
        scope=ReportScope.SPL,
        project_name="MyProduct",
        variant_data=VariantReportData(
            files=[
                _variant_link("Disco", "gtest", "variants/Disco/gtest/index.html"),
                _variant_link("Disco", "arduino", "variants/Disco/arduino/index.html"),
            ]
        ),
    )


def test_spl_report_round_trip(tmp_path: Path) -> None:
    restored = ReportData.from_dict(_spl_report(tmp_path).to_dict())
    assert restored.scope == ReportScope.SPL
    assert restored.has_spl_scope and not restored.has_variant_scope and not restored.has_component_scope
    assert restored.title == "MyProduct"
    assert restored.variant_data is not None
    assert [c.name for c in restored.variant_data.html_content] == ["Disco (gtest)", "Disco (arduino)"]


def test_sphinx_config_loads_spl_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = _write_config(tmp_path, _spl_report(tmp_path).to_dict())
    monkeypatch.setenv(SphinxConfig.REPORT_CONFIGURATION_FILE_ENV_NAME, str(config_file))

    config = SphinxConfig()

    assert isinstance(config.report_data, SphinxReportConfig)  # one payload class for every scope
    assert config.report_data.has_spl_scope
    assert config.project == "MyProduct"
    # SPL variant links render through the very same helper variant reports use.
    links = config.report_data.get_variant_files_list()
    assert any("Disco (gtest)" in entry and "variants/Disco/gtest/index.html" in entry for entry in links)


def test_sphinx_config_loads_variant_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = ReportData(project_dir=tmp_path, scope=ReportScope.VARIANT, variant_name="Disco", platform_name="gtest")
    config_file = _write_config(tmp_path, payload.to_dict())
    monkeypatch.setenv(SphinxConfig.REPORT_CONFIGURATION_FILE_ENV_NAME, str(config_file))

    config = SphinxConfig()

    assert config.report_data is not None
    assert config.report_data.has_variant_scope
    assert not config.report_data.has_spl_scope
    assert config.project == "Disco"


def test_sphinx_config_no_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SphinxConfig.REPORT_CONFIGURATION_FILE_ENV_NAME, raising=False)
    config = SphinxConfig()
    assert config.report_data is None
    assert config.project == "Unknown"
