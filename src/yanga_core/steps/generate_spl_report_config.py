"""Write the SPL-scope report_config.json for the SPL documentation report."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mashumaro import DataClassDictMixin
from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.generated_file import GeneratedFile
from yanga_core.domain.reports import REPORT_CONFIG_FILE_NAME, ReportData, ReportScope
from yanga_core.steps.register_spl_paths import get_registered_spl_paths


@dataclass
class GenerateSplReportConfigConfig(DataClassDictMixin):
    #: Product-line display name shown as the report title; defaults to the project directory name.
    project_name: str = ""


class GenerateSplReportConfig(PipelineStep[ExecutionContext]):
    """
    Build the config of the SPL documentation report.

    The SPL analogue of GenerateReportConfig: the project's index.md branches on scope=SPL to
    document what belongs to the whole product line. The variants are listed by the SPL overview,
    not here.
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

    def run(self) -> int:
        config = ReportData(
            project_dir=self.project_root_dir,
            scope=ReportScope.SPL,
            project_name=self.user_config.project_name or self.project_root_dir.name,
        )
        GeneratedFile(self.report_config_file, config.to_json_string()).to_file()
        self.logger.info(f"Wrote SPL report config to {self.report_config_file}")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        # Not statically known: the output root comes from the registered SPLPaths at run time.
        return []

    def update_execution_context(self) -> None:
        pass
