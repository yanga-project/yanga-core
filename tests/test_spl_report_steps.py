"""
Test the SPL report pipeline steps.

The four steps run from a separate pypeline config (no variant slurp, no `--variant/--platform`)
and turn already-built variant reports into one SPL overview site:

```yaml
# spl_pypeline.yaml — run with `pypeline run --config-file spl_pypeline.yaml`
pipeline:
  spl:
    - step: RegisterSplPaths
      module: yanga_core.steps.register_spl_paths
    - step: CollectVariantReports
      module: yanga_core.steps.collect_variant_reports
    - step: GenerateSplReportConfig
      module: yanga_core.steps.generate_spl_report_config
      config:
        project_name: MySPL
    - step: SphinxBuildReport
      module: yanga_core.steps.sphinx_build_report
```
"""

from pathlib import Path

import pytest
from py_app_dev.core.exceptions import UserNotificationException
from pypeline.domain.execution_context import ExecutionContext

from yanga_core.domain.reports import REPORT_CONFIG_FILE_NAME, ReportData, ReportScope
from yanga_core.steps.collect_variant_reports import CollectedVariantReport, CollectVariantReports
from yanga_core.steps.generate_spl_report_config import GenerateSplReportConfig
from yanga_core.steps.register_spl_paths import RegisterSplPaths, get_registered_spl_paths
from yanga_core.steps.sphinx_build_report import SphinxBuildReport


def create_context_with_registered_paths(tmp_path: Path) -> ExecutionContext:
    context = ExecutionContext(project_root_dir=tmp_path)
    assert RegisterSplPaths(context).run() == 0
    return context


def create_built_variant_report(project_root: Path, variant: str, platform: str, build_type: str | None = None) -> Path:
    """Simulate a variant build: the report_config.json marker next to the rendered reports/ dir."""
    variant_build_dir = project_root.joinpath(".yanga/build/variants", *(part for part in (variant, platform, build_type) if part))
    report_dir = variant_build_dir / "reports"
    report_dir.mkdir(parents=True)
    (report_dir / "index.html").write_text("<html></html>")
    marker = ReportData(project_dir=project_root, variant_name=variant, platform_name=platform, build_type=build_type)
    (variant_build_dir / REPORT_CONFIG_FILE_NAME).write_text(marker.to_json_string())
    return report_dir


def test_register_spl_paths_defaults_to_yanga_dir(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)

    assert get_registered_spl_paths(context).spl_report_dir == tmp_path / ".yanga/build/spl/reports"


def test_register_spl_paths_honors_create_yanga_build_dir(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.yanga]\ncreate_yanga_build_dir = false\n")

    context = create_context_with_registered_paths(tmp_path)

    assert get_registered_spl_paths(context).spl_report_dir == tmp_path / "build/spl/reports"


def test_spl_steps_require_registered_paths(tmp_path: Path) -> None:
    context = ExecutionContext(project_root_dir=tmp_path)
    with pytest.raises(UserNotificationException, match="RegisterSplPaths"):
        CollectVariantReports(context).run()


def test_collect_variant_reports_gathers_only_built_reports(tmp_path: Path) -> None:
    report_dir = create_built_variant_report(tmp_path, "V1", "p1")
    (report_dir / "style.css").write_text("")
    # V2 has a marker but rendered no report; it shall be skipped silently.
    (tmp_path / ".yanga/build/variants/V2/p1").mkdir(parents=True)
    marker = ReportData(project_dir=tmp_path, variant_name="V2", platform_name="p1")
    (tmp_path / ".yanga/build/variants/V2/p1" / REPORT_CONFIG_FILE_NAME).write_text(marker.to_json_string())
    context = create_context_with_registered_paths(tmp_path)

    assert CollectVariantReports(context).run() == 0

    assert (tmp_path / ".yanga/build/spl/reports/variants/V1/p1/index.html").is_file()
    assert (tmp_path / ".yanga/build/spl/reports/variants/V1/p1/style.css").is_file()
    collected = context.data_registry.find_data(CollectedVariantReport)
    assert [(entry.variant, entry.platform) for entry in collected] == [("V1", "p1")]
    assert collected[0].index_html == Path("variants/V1/p1/index.html")


def test_collect_variant_reports_discovers_build_type_builds(tmp_path: Path) -> None:
    # Regression: reports rendered under a build-type dir (variants/<v>/<p>/<bt>/reports) were missed
    # when collection iterated the project config instead of discovering markers on disk.
    create_built_variant_report(tmp_path, "V1", "p1", "Debug")
    context = create_context_with_registered_paths(tmp_path)

    assert CollectVariantReports(context).run() == 0

    collected = context.data_registry.find_data(CollectedVariantReport)
    assert [(entry.variant, entry.platform, entry.build_type) for entry in collected] == [("V1", "p1", "Debug")]
    assert collected[0].index_html == Path("variants/V1/p1/Debug/index.html")
    assert (tmp_path / ".yanga/build/spl/reports/variants/V1/p1/Debug/index.html").is_file()


def test_collect_variant_reports_skips_component_markers(tmp_path: Path) -> None:
    # Component builds write their own report_config.json (and reports/) inside the variant build
    # tree; only the variant-scope marker denotes a collectible report.
    create_built_variant_report(tmp_path, "V1", "p1")
    component_dir = tmp_path / ".yanga/build/variants/V1/p1/comp_a"
    (component_dir / "reports").mkdir(parents=True)
    (component_dir / "reports/index.html").write_text("<html></html>")
    component_marker = ReportData(project_dir=tmp_path, scope=ReportScope.COMPONENT, component_name="comp_a")
    (component_dir / REPORT_CONFIG_FILE_NAME).write_text(component_marker.to_json_string())
    context = create_context_with_registered_paths(tmp_path)

    assert CollectVariantReports(context).run() == 0

    collected = context.data_registry.find_data(CollectedVariantReport)
    assert [(entry.variant, entry.platform) for entry in collected] == [("V1", "p1")]


def test_collect_variant_reports_skips_unreadable_marker(tmp_path: Path) -> None:
    variant_build_dir = tmp_path / ".yanga/build/variants/V1/p1"
    (variant_build_dir / "reports").mkdir(parents=True)
    (variant_build_dir / "reports/index.html").write_text("<html></html>")
    (variant_build_dir / REPORT_CONFIG_FILE_NAME).write_text("not json {")
    context = create_context_with_registered_paths(tmp_path)

    assert CollectVariantReports(context).run() == 0

    assert context.data_registry.find_data(CollectedVariantReport) == []


def test_collect_variant_reports_rejects_unknown_source(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)
    step = CollectVariantReports(context, config={"source": "github-release"})
    with pytest.raises(UserNotificationException, match="github-release"):
        step.run()


def test_generate_spl_report_config_writes_sorted_variant_links(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)
    context.data_registry.insert(CollectedVariantReport(variant="V2", platform="p1", index_html=Path("variants/V2/p1/index.html")), "test")
    context.data_registry.insert(CollectedVariantReport(variant="V1", platform="p1", index_html=Path("variants/V1/p1/Debug/index.html"), build_type="Debug"), "test")
    context.data_registry.insert(CollectedVariantReport(variant="V1", platform="p1", index_html=Path("variants/V1/p1/index.html")), "test")

    assert GenerateSplReportConfig(context, config={"project_name": "MySPL"}).run() == 0

    config = ReportData.from_json_file(tmp_path / ".yanga/build/spl/reports/report_config.json")
    assert config.scope == ReportScope.SPL
    assert config.has_spl_scope and not config.has_variant_scope and not config.has_component_scope
    assert config.title == "MySPL"
    assert config.variant_data is not None
    assert [entry.html_content.name for entry in config.variant_data.files if entry.html_content] == ["V1 (p1)", "V1 (p1, Debug)", "V2 (p1)"]


def test_generate_spl_report_config_project_name_defaults_to_dir_name(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)

    assert GenerateSplReportConfig(context).run() == 0

    config = ReportData.from_json_file(tmp_path / ".yanga/build/spl/reports/report_config.json")
    assert config.title == tmp_path.name


def test_sphinx_build_report_requires_report_config(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)
    with pytest.raises(UserNotificationException, match="GenerateSplReportConfig"):
        SphinxBuildReport(context).run()


def test_sphinx_build_report_makes_external_links_open_in_new_tab(tmp_path: Path) -> None:
    output_root = tmp_path / ".yanga/build/spl/reports"
    output_root.mkdir(parents=True)
    (output_root / "report_config.json").write_text("{}")
    context = create_context_with_registered_paths(tmp_path)

    class FakeSphinx:
        def execute(self) -> None:
            (output_root / "index.html").write_text('<a href="./variants/V1/p1/index.html#http://">V1 (p1)</a>')

    context.create_process_executor = lambda command, cwd=None: FakeSphinx()  # type: ignore[method-assign, assignment, return-value, unused-ignore]

    assert SphinxBuildReport(context).run() == 0

    assert 'href="variants/V1/p1/index.html" target="_blank" rel="noopener"' in (output_root / "index.html").read_text()
