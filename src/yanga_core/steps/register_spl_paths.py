"""Resolve the yanga project settings once and register them for the SPL report steps."""

from pathlib import Path
from typing import Any

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.spl_paths import SPLPaths
from yanga_core.ini import YangaIni


def get_registered_spl_paths(execution_context: ExecutionContext) -> SPLPaths:
    """The project-scope SPLPaths registered by RegisterSplPaths; the single path authority for the SPL report steps."""
    found = execution_context.data_registry.find_data(SPLPaths)
    if not found:
        raise UserNotificationException("No SPLPaths registered. Add the RegisterSplPaths step (yanga_core.steps.register_spl_paths) before this step.")
    return found[-1]


class RegisterSplPaths(PipelineStep[ExecutionContext]):
    """
    Register a project-scope SPLPaths for the SPL report steps.

    Reads the project settings (yanga.ini / pyproject.toml) once; downstream steps resolve every
    path through the registered SPLPaths instead of interpreting the settings themselves.
    """

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_needs_dependency_management(self) -> bool:
        # Always run so the registry is populated for the downstream steps.
        return False

    def run(self) -> int:
        ini = YangaIni.from_toml_or_ini(self.project_root_dir / "yanga.ini", self.project_root_dir / "pyproject.toml")
        spl_paths = SPLPaths(self.project_root_dir, None, None, None, create_yanga_build_dir=ini.create_yanga_build_dir)
        self.execution_context.data_registry.insert(spl_paths, self.get_name())
        self.logger.info(f"SPL report output root: {spl_paths.spl_report_dir}")
        return 0

    def get_inputs(self) -> list[Path]:
        return [self.project_root_dir / "yanga.ini", self.project_root_dir / "pyproject.toml"]

    def get_outputs(self) -> list[Path]:
        return []

    def update_execution_context(self) -> None:
        pass
