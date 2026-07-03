"""Render a report with Sphinx from a generated report_config.json (used for the SPL report)."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mashumaro import DataClassDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.commands.fix_html_links import fix_html_links
from yanga_core.docs.sphinx import SphinxConfig
from yanga_core.domain.reports import REPORT_CONFIG_FILE_NAME
from yanga_core.steps.register_spl_paths import get_registered_spl_paths


@dataclass
class SphinxBuildReportConfig(DataClassDictMixin):
    #: Sphinx source directory (holds conf.py + the master index.md), relative to the project root.
    source_dir: str = "."


class SphinxBuildReport(PipelineStep[ExecutionContext]):
    """Run sphinx-build over the project's conf.py/index.md, pointed at the generated SPL report config."""

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.user_config = SphinxBuildReportConfig.from_dict(config) if config else SphinxBuildReportConfig()

    @property
    def output_root(self) -> Path:
        return get_registered_spl_paths(self.execution_context).spl_report_dir

    @property
    def report_config_file(self) -> Path:
        return self.output_root / REPORT_CONFIG_FILE_NAME

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_needs_dependency_management(self) -> bool:
        return False

    def run(self) -> int:
        if not self.report_config_file.is_file():
            raise UserNotificationException(f"Report config not found at {self.report_config_file}; run GenerateSplReportConfig first.")
        source_dir = self.project_root_dir / self.user_config.source_dir
        self.execution_context.add_env_vars({SphinxConfig.REPORT_CONFIGURATION_FILE_ENV_NAME: str(self.report_config_file)})
        executor = self.execution_context.create_process_executor(
            [sys.executable, "-m", "sphinx", "-b", "html", str(source_dir), str(self.output_root)],
            cwd=self.project_root_dir,
        )
        executor.execute()
        results = fix_html_links(self.output_root)
        for failure in (result for result in results if not result.success):
            self.logger.warning(failure.error_message)
        self.logger.info(f"Rendered SPL report to {self.output_root} ({sum(r.fixes_count for r in results)} external artifact links fixed)")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        # Not statically known: the output root comes from the registered SPLPaths at run time.
        return []

    def update_execution_context(self) -> None:
        pass
