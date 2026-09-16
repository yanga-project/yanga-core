import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mashumaro import DataClassDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.execution_context import ExecutionContext


@dataclass
class KConfigEditRequest(DataClassDictMixin):
    """The flags of ``UserRequest.extra`` this step understands."""

    gui: bool = True


@dataclass
class KConfigEditScope:
    model_file: Path
    #: The file the editor loads and saves
    selection_file: Path


class KConfigEdit(PipelineStep[ExecutionContext]):
    """
    Opens kconfiglib's editor on the requested feature model and saves into its declared selection file.

    Only declared selection files are edited, since code generation reads nothing else.
    Without a variant and a platform it shows the product selection of all variants in kspl's viewer.
    A platform whose model needs its own tool declares that tool in its ``feature_model:`` pipeline instead.
    """

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()

    def get_name(self) -> str:
        return self.__class__.__name__

    @property
    def scope(self) -> KConfigEditScope:
        context = self.execution_context
        variant = context.variant
        platform_name = context.user_request.platform_name
        if not variant:
            raise UserNotificationException("Select a variant to edit a feature selection.")
        if not platform_name:
            if not context.feature_model:
                raise UserNotificationException("The project declares no 'feature_model:' block.")
            selection_file = context.variant_feature_selection_file
            if not selection_file:
                raise UserNotificationException(f"Variant '{variant.name}' has no 'feature_selection:' configured.")
            return KConfigEditScope(Path(context.feature_model.file), selection_file)
        platform = context.platform
        if not platform or not platform.feature_model:
            raise UserNotificationException(f"Platform '{platform_name}' declares no 'feature_model:' block.")
        selection_file = context.variant_platform_feature_selection_file
        if not selection_file:
            raise UserNotificationException(f"Variant '{variant.name}' has no 'feature_selection:' configured for platform '{platform_name}'.")
        return KConfigEditScope(Path(platform.feature_model.file), selection_file)

    def create_command(self, scope: KConfigEditScope) -> list[str]:
        request = KConfigEditRequest.from_dict(self.execution_context.user_request.extra)
        # kconfiglib's own editors, the way they are run by hand: the model as argument, the file through KCONFIG_CONFIG.
        return [sys.executable, "-m", "guiconfig" if request.gui else "menuconfig", str(scope.model_file)]

    @property
    def is_overview(self) -> bool:
        return not self.execution_context.variant and not self.execution_context.user_request.platform_name

    def create_overview_command(self) -> list[str]:
        if not self.execution_context.feature_model:
            raise UserNotificationException("The project declares no 'feature_model:' block.")
        if not KConfigEditRequest.from_dict(self.execution_context.user_request.extra).gui:
            raise UserNotificationException("The overview of all variants has no terminal view; select a variant or a platform to use the terminal editor.")
        return [sys.executable, "-m", "yanga_core.commands", "kconfig_view", "--project-dir", str(self.project_root_dir)]

    def run(self) -> int:
        env = self.execution_context.create_process_env()
        if self.is_overview:
            command, cwd = self.create_overview_command(), self.project_root_dir
        else:
            scope = self.scope
            command, cwd = self.create_command(scope), scope.model_file.parent
            env["KCONFIG_CONFIG"] = str(scope.selection_file)
        self.logger.info(f"Run {' '.join(command)}")
        # Not the process executor: it captures the output, and the terminal editor needs the terminal.
        # The pipeline's environment is passed on, since the model may read variables set by earlier steps.
        # The model directory is the working directory, as for KConfigGen, so relative 'source' paths resolve the same.
        result = subprocess.run(command, env=env, cwd=cwd, check=False)  # noqa: S603
        if result.returncode:
            raise UserNotificationException(f"The KConfig editor exited with code {result.returncode}.")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        return []

    def update_execution_context(self) -> None:
        pass
