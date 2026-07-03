"""Turn the collected variant reports into an SPL-scope report_config.json for Sphinx."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mashumaro import DataClassDictMixin
from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.execution_context import UserRequest, UserRequestScope, UserRequestTarget
from yanga_core.domain.generated_file import GeneratedFile
from yanga_core.domain.reports import (
    REPORT_CONFIG_FILE_NAME,
    ReportData,
    ReportRelevantFiles,
    ReportRelevantFileType,
    ReportRelevantHtmlContent,
    ReportScope,
    VariantReportData,
)
from yanga_core.steps.collect_variant_reports import CollectedVariantReport
from yanga_core.steps.register_spl_paths import get_registered_spl_paths


@dataclass
class GenerateSplReportConfigConfig(DataClassDictMixin):
    #: Product-line display name shown as the report title; defaults to the project directory name.
    project_name: str = ""


class GenerateSplReportConfig(PipelineStep[ExecutionContext]):
    """
    Build the SPL report config from the collected variant reports.

    This is the SPL analogue of GenerateReportConfig: same idea (produce the config the Sphinx
    renderer consumes), but its source is the collected variant reports, not a live build's
    registry. A variant link is just a reference to generated HTML, so the SPL report reuses the
    ordinary ReportData shape with scope=SPL — no bespoke payload.
    """

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.user_config = GenerateSplReportConfigConfig.from_dict(config) if config else GenerateSplReportConfigConfig()

    @property
    def report_config_file(self) -> Path:
        return get_registered_spl_paths(self.execution_context).spl_report_dir / REPORT_CONFIG_FILE_NAME

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_needs_dependency_management(self) -> bool:
        return False

    @staticmethod
    def _link_name(report: CollectedVariantReport) -> str:
        scope = f"{report.platform}, {report.build_type}" if report.build_type else report.platform
        return f"{report.variant} ({scope})"

    def run(self) -> int:
        collected = sorted(
            self.execution_context.data_registry.find_data(CollectedVariantReport),
            key=lambda c: (c.variant, c.platform, c.build_type or ""),
        )
        variant_links = [
            ReportRelevantFiles(
                # A per-variant link is a reference to generated HTML; the target is build-wiring
                # metadata the renderer ignores (kept only because the field is still required here).
                target=UserRequest(UserRequestScope.VARIANT, variant_name=report.variant, target=UserRequestTarget.NONE),
                file_type=ReportRelevantFileType.HTML,
                files_to_be_included=[],
                html_content=ReportRelevantHtmlContent(name=self._link_name(report), index_html=report.index_html),
            )
            for report in collected
        ]
        config = ReportData(
            project_dir=self.project_root_dir,
            scope=ReportScope.SPL,
            project_name=self.user_config.project_name or self.project_root_dir.name,
            variant_data=VariantReportData(files=variant_links),
        )
        GeneratedFile(self.report_config_file, config.to_json_string()).to_file()
        self.logger.info(f"Wrote SPL report config with {len(variant_links)} variant link(s) to {self.report_config_file}")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        # Not statically known: the output root comes from the registered SPLPaths at run time.
        return []

    def update_execution_context(self) -> None:
        pass
