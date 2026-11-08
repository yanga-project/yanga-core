"""
Test the SPL report pipeline steps.

Each variant build ends with WritePublishManifest. A separate pypeline config (no variant slurp, no
`--variant/--platform`) builds the SPL documentation report, writes its manifest, and renders the
overview from all manifests:

```yaml
# spl_pypeline.yaml, run with `pypeline run --config-file spl_pypeline.yaml`
pipeline:
  - step: RegisterSplPaths
    description: Read the build directory settings from yanga.ini or pyproject.toml
    module: yanga_core.steps.register_spl_paths
  - step: GenerateSplReportConfig
    description: Write the report config that makes index.md render its SPL branch
    module: yanga_core.steps.generate_spl_report_config
    config:
      project_name: MySPL
  - step: SphinxBuildReport
    description: Build conf.py and index.md into .yanga/build/spl/reports
    module: yanga_core.steps.sphinx_build_report
  - step: WritePublishManifest
    description: Record the SPL documentation in .yanga/build/spl/publish_manifest.json
    module: yanga_core.steps.write_publish_manifest
  - step: CollectPublishManifests
    description: Read the manifests the variant builds left under .yanga/build/variants
    module: yanga_core.steps.collect_publish_manifests
  - step: RenderSplOverview
    description: Fill spl_overview.html.jinja and write .yanga/build/index.html
    module: yanga_core.steps.render_spl_overview
    config:
      project_name: MySPL
```
"""

from pathlib import Path

import pytest
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext

from yanga_core.domain.config import PlatformConfig, VariantConfig
from yanga_core.domain.execution_context import ExecutionContext as YangaExecutionContext
from yanga_core.domain.execution_context import UserRequest, UserRequestScope
from yanga_core.domain.publish_manifest import PUBLISH_MANIFEST_FILE_NAME, ManifestEntry, PublishedFile, PublishKind, PublishManifest
from yanga_core.domain.reports import FeaturesReportRelevantFile, ReportData, ReportScope
from yanga_core.steps.collect_publish_manifests import CollectPublishManifests
from yanga_core.steps.generate_spl_report_config import GenerateSplReportConfig
from yanga_core.steps.register_spl_paths import RegisterSplPaths, get_registered_spl_paths
from yanga_core.steps.render_spl_overview import RenderSplOverview, create_overview
from yanga_core.steps.sphinx_build_report import SphinxBuildReport
from yanga_core.steps.write_publish_manifest import WritePublishManifest


def create_context_with_registered_paths(tmp_path: Path) -> ExecutionContext:
    context = ExecutionContext(project_root_dir=tmp_path)
    assert RegisterSplPaths(context).run() == 0
    return context


def write_file(file: Path, content: str = "") -> Path:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content)
    return file


def write_manifest(file: Path, manifest: PublishManifest) -> None:
    write_file(file, manifest.to_json_string())


def variant_manifest(
    variant: str,
    platform: str,
    build_time: str = "2026-11-04T10:00:00+00:00",
    build_type: str | None = None,
    description: str | None = None,
    entries: list[ManifestEntry] | None = None,
) -> PublishManifest:
    return PublishManifest(
        scope=ReportScope.VARIANT,
        build_time=build_time,
        variant=variant,
        platform=platform,
        build_type=build_type,
        description=description,
        entries=entries or [],
    )


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
        CollectPublishManifests(context).run()


def test_write_publish_manifest_for_a_variant_build(tmp_path: Path) -> None:
    context = YangaExecutionContext(
        tmp_path,
        UserRequest(UserRequestScope.VARIANT, variant_name="V1", build_type="Debug"),
        variant_name="V1",
        platform=PlatformConfig(name="p1"),
        variant=VariantConfig(name="V1", description="The first variant"),
    )
    build_dir = tmp_path / ".yanga/build/variants/V1/p1/Debug"
    features_file = write_file(build_dir / "kconfig/autoconf.json", '{"BLINKING": true, "PERIOD": 10}')
    context.data_registry.insert(FeaturesReportRelevantFile(provider="test", json_config_file=features_file), "test")
    context.data_registry.insert(PublishedFile(PublishKind.REPORT, "Variant report", write_file(build_dir / "reports/index.html")), "test")
    # Registered, but the requested target did not make it: not listed.
    context.data_registry.insert(PublishedFile(PublishKind.ARTIFACT, "Executable", build_dir / "app.exe"), "test")

    assert WritePublishManifest(context).run() == 0

    manifest = PublishManifest.from_json_file(build_dir / PUBLISH_MANIFEST_FILE_NAME)
    assert (manifest.scope, manifest.variant, manifest.platform, manifest.build_type) == (ReportScope.VARIANT, "V1", "p1", "Debug")
    assert manifest.description == "The first variant"
    assert manifest.features == {"BLINKING": True, "PERIOD": 10}
    assert manifest.entries == [ManifestEntry(PublishKind.REPORT, "Variant report", "variants/V1/p1/Debug/reports/index.html")]


def test_write_publish_manifest_for_the_spl_documentation_report(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)
    report = write_file(tmp_path / ".yanga/build/spl/reports/index.html")
    context.data_registry.insert(PublishedFile(PublishKind.REPORT, "SPL documentation", report), "test")

    assert WritePublishManifest(context).run() == 0

    manifest = PublishManifest.from_json_file(tmp_path / ".yanga/build/spl" / PUBLISH_MANIFEST_FILE_NAME)
    assert manifest.scope == ReportScope.SPL
    assert manifest.entries == [ManifestEntry(PublishKind.REPORT, "SPL documentation", "spl/reports/index.html")]


def test_write_publish_manifest_refuses_outputs_outside_the_site_root(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)
    context.data_registry.insert(PublishedFile(PublishKind.ARTIFACT, "Elsewhere", write_file(tmp_path / "elsewhere.hex")), "test")

    with pytest.raises(UserNotificationException, match="outside the site root"):
        WritePublishManifest(context).run()


def test_collect_publish_manifests_finds_variant_and_spl_manifests(tmp_path: Path) -> None:
    write_manifest(tmp_path / ".yanga/build/variants/V1/p1/Debug" / PUBLISH_MANIFEST_FILE_NAME, variant_manifest("V1", "p1", build_type="Debug"))
    write_manifest(tmp_path / ".yanga/build/spl" / PUBLISH_MANIFEST_FILE_NAME, PublishManifest(scope=ReportScope.SPL, build_time="t"))
    write_manifest(tmp_path / ".yanga/build/spl/reports/_static" / PUBLISH_MANIFEST_FILE_NAME, PublishManifest(scope=ReportScope.SPL, build_time="not the SPL manifest"))
    write_file(tmp_path / ".yanga/build/variants/V2/p1" / PUBLISH_MANIFEST_FILE_NAME, "not json {")
    context = create_context_with_registered_paths(tmp_path)

    assert CollectPublishManifests(context).run() == 0

    collected = context.data_registry.find_data(PublishManifest)
    assert sorted((manifest.scope.name, manifest.variant, manifest.build_time) for manifest in collected if manifest.scope == ReportScope.SPL) == [("SPL", None, "t")]
    assert sorted(manifest.variant or "" for manifest in collected) == ["", "V1"]


def test_collect_publish_manifests_warns_when_no_variant_was_built(tmp_path: Path) -> None:
    write_manifest(tmp_path / ".yanga/build/spl" / PUBLISH_MANIFEST_FILE_NAME, PublishManifest(scope=ReportScope.SPL, build_time="t"))
    context = create_context_with_registered_paths(tmp_path)
    messages: list[str] = []
    sink = logger.add(messages.append, level="WARNING")

    try:
        assert CollectPublishManifests(context).run() == 0
    finally:
        logger.remove(sink)

    assert any("build a variant first" in message for message in messages)


def test_create_overview_groups_builds_by_variant_with_the_newest_facts() -> None:
    manifests = [
        variant_manifest("V2", "p1"),
        variant_manifest("V1", "p2", build_time="2026-11-04T09:00:00+00:00", description="old"),
        variant_manifest(
            "V1",
            "p1",
            description="new",
            entries=[
                ManifestEntry(PublishKind.REPORT, "Variant report", "variants/V1/p1/reports/index.html"),
                ManifestEntry(PublishKind.ARTIFACT, "Executable", "variants/V1/p1/app.exe"),
            ],
        ),
        PublishManifest(scope=ReportScope.SPL, build_time="t", commit="abc", entries=[ManifestEntry(PublishKind.REPORT, "SPL documentation", "spl/reports/index.html")]),
    ]

    overview = create_overview("MySPL", manifests)

    assert overview.commit == "abc"
    assert [entry.link for entry in overview.documentation] == ["spl/reports/index.html"]
    assert [(variant.name, variant.description) for variant in overview.variants] == [("V1", "new"), ("V2", None)]
    first_build = overview.variants[0].builds[0]
    assert [build.platform for build in overview.variants[0].builds] == ["p1", "p2"]
    assert [entry.name for entry in first_build.reports] == ["Variant report"]
    assert [entry.name for entry in first_build.artifacts] == ["Executable"]


def test_render_spl_overview_writes_the_project_template_to_the_site_root(tmp_path: Path) -> None:
    write_file(tmp_path / "spl_overview.html.jinja", "{{ overview.project_name }}:{% for v in overview.variants %}{{ v.name }}{% endfor %}")
    context = create_context_with_registered_paths(tmp_path)
    context.data_registry.insert(variant_manifest("V1", "p1"), "test")

    assert RenderSplOverview(context, config={"project_name": "MySPL"}).run() == 0

    assert (tmp_path / ".yanga/build/index.html").read_text() == "MySPL:V1"


def test_render_spl_overview_requires_the_template(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)
    with pytest.raises(UserNotificationException, match="template not found"):
        RenderSplOverview(context).run()


def test_generate_spl_report_config_writes_spl_scope(tmp_path: Path) -> None:
    context = create_context_with_registered_paths(tmp_path)

    assert GenerateSplReportConfig(context, config={"project_name": "MySPL"}).run() == 0

    config = ReportData.from_json_file(tmp_path / ".yanga/build/spl/reports/report_config.json")
    assert config.scope == ReportScope.SPL
    assert config.has_spl_scope and not config.has_variant_scope and not config.has_component_scope
    assert config.title == "MySPL"
    assert config.variant_data is None


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
    assert context.data_registry.find_data(PublishedFile) == [PublishedFile(PublishKind.REPORT, "SPL documentation", output_root / "index.html")]
