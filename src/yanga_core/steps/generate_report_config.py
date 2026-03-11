from pathlib import Path
from typing import Any

from py_app_dev.core.logging import logger
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.execution_context import ExecutionContext
from yanga_core.domain.generated_file import GeneratedFile
from yanga_core.domain.reports import (
    ComponentReportData,
    FeaturesReportRelevantFile,
    ReportData,
    ReportRelevantFiles,
    VariantReportData,
)


class GenerateReportConfig(PipelineStep[ExecutionContext]):
    """Generate the variant report_config.json from all registered ReportRelevantFiles."""

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()

    @property
    def output_dir(self) -> Path:
        return self.execution_context.spl_paths.variant_build_dir

    @property
    def report_config_file(self) -> Path:
        return self.output_dir / "report_config.json"

    def get_name(self) -> str:
        return self.__class__.__name__

    def run(self) -> int:
        self.logger.info(f"Run {self.get_name()}")
        relevant_files_entries = self.execution_context.data_registry.find_data(ReportRelevantFiles)

        components_data: dict[str, list[ReportRelevantFiles]] = {}
        variant_data: list[ReportRelevantFiles] = []
        for entry in relevant_files_entries:
            if entry.target.component_name:
                if entry.target.component_name in components_data:
                    components_data[entry.target.component_name].append(entry)
                else:
                    components_data[entry.target.component_name] = [entry]
            else:
                variant_data.append(entry)

        config = ReportData(
            variant_name=self.execution_context.variant_name or "",
            platform_name=self.execution_context.platform.name if self.execution_context.platform else "",
            project_dir=self.execution_context.project_root_dir,
            components=[
                ComponentReportData(
                    name=component_name,
                    files=files,
                    build_dir=self.execution_context.spl_paths.get_component_build_dir(component_name),
                )
                for component_name, files in components_data.items()
            ],
        )
        if variant_data:
            config.variant_data = VariantReportData(
                files=variant_data,
                build_dir=self.execution_context.spl_paths.variant_build_dir,
            )
        features_config_files = self.execution_context.data_registry.find_data(FeaturesReportRelevantFile)
        if features_config_files:
            config.features_json_config = features_config_files[0].json_config_file

        GeneratedFile(self.report_config_file, config.to_json_string()).to_file()
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        return [self.report_config_file]

    def update_execution_context(self) -> None:
        pass
