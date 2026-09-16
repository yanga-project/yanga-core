"""
Command line utility to view the product feature selection of all variants with kspl.

The ``KConfigEdit`` step runs it as its own process, with the pipeline's environment:

    python -m yanga_core.commands kconfig_view --project-dir .
"""

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path

from kspl.config_slurper import KConfigData, VariantData, VariantViewData
from kspl.kconfig import EditableConfigElement, KConfig
from mashumaro import DataClassDictMixin
from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from py_app_dev.mvp.event_manager import EventManager

from yanga_core.domain.config import VariantConfig
from yanga_core.domain.spl_paths import SPLPaths

from .base import create_config
from .run import RunCommand


class ProductFeaturesData(KConfigData):
    """The project's product feature model with each variant's declared selection, for kspl's viewer."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir.absolute()
        self.refresh_data()

    def refresh_data(self) -> None:
        project_slurper = RunCommand.create_project_slurper(self.project_dir)
        if not project_slurper.feature_model:
            raise UserNotificationException("The project declares no 'feature_model:' block.")
        model_file = Path(project_slurper.feature_model.file)
        self.model: KConfig = KConfig(model_file)
        self.variants: list[VariantData] = [VariantData(variant.name, KConfig(model_file, self._selection_file(variant))) for variant in project_slurper.variants] or [
            VariantData("Default", self.model)
        ]

    def _selection_file(self, variant: VariantConfig) -> Path | None:
        if not variant.feature_selection:
            return None
        return SPLPaths(self.project_dir, variant.name, None, None).locate_artifact(variant.feature_selection.file, [variant.file])

    def get_elements(self) -> list[EditableConfigElement]:
        return self.model.elements

    def get_variants(self) -> list[VariantViewData]:
        return [VariantViewData(variant.name, {element.name: element.value for element in variant.config.elements if not element.is_menu}) for variant in self.variants]

    def find_variant_config(self, variant_name: str) -> VariantData | None:
        return next((variant for variant in self.variants if variant.name == variant_name), None)


@dataclass
class KConfigViewCommandConfig(DataClassDictMixin):
    project_dir: Path = field(
        metadata={"help": "Project root directory."},
    )


class KConfigViewCommand(Command):
    def __init__(self) -> None:
        super().__init__("kconfig_view", "View the product feature selection of all variants.")
        self.logger = logger.bind()

    def run(self, args: Namespace) -> int:
        self.logger.info(f"Running {self.name} with args {args}")
        config = create_config(KConfigViewCommandConfig, args)
        data = ProductFeaturesData(config.project_dir)
        # Imported here: the viewer needs Tk, loading the data does not.
        from kspl.gui import KSPL

        KSPL(EventManager(), data).run()
        return 0

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, KConfigViewCommandConfig)
