from argparse import ArgumentParser, BooleanOptionalAction, Namespace
from dataclasses import dataclass, field

from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, time_it

from yanga_core.domain.config import FeatureModelConfig
from yanga_core.domain.execution_context import UserRequest, UserRequestScope, UserRequestTarget
from yanga_core.domain.project_slurper import YangaProjectSlurper

from .base import CommandConfigBase, create_config
from .run import RunCommand


@dataclass
class FeaturesCommandConfig(CommandConfigBase):
    variant_name: str | None = field(
        default=None,
        metadata={"help": "Variant whose selection to edit. Alone it edits the product selection; with --platform, the variant's selection for that platform."},
    )
    platform: str | None = field(
        default=None,
        metadata={"help": "Platform whose feature model to open, together with --variant. Without both, all variants' product selections are shown."},
    )
    gui: bool = field(
        default=True,
        metadata={"help": "Use the GUI editor; pass --no-gui for the terminal editor.", "action": BooleanOptionalAction},
    )


class FeaturesCommand(Command):
    def __init__(self) -> None:
        super().__init__("features", "Show the product features of all variants, or edit the selection of a variant and/or a platform.")
        self.logger = logger.bind()

    @time_it("Features")
    def run(self, args: Namespace) -> int:
        self.logger.debug(f"Running {self.name} with args {args}")
        return self.do_run(create_config(FeaturesCommandConfig, args))

    def do_run(self, config: FeaturesCommandConfig) -> int:
        if config.platform and not config.variant_name:
            # A platform model is opened by the platform's own tool, which configures a build of a variant.
            raise UserNotificationException(f"Platform '{config.platform}' needs --variant: a platform's selection cannot be edited on its own.")
        project_slurper = RunCommand.create_project_slurper(config.project_dir)
        variant_name = config.variant_name
        feature_model = self.select_feature_model(project_slurper, config.platform)
        self.logger.info(f"Open feature model: {feature_model.description or feature_model.file}")
        RunCommand.execute_pipeline_steps(
            project_dir=config.project_dir,
            project_slurper=project_slurper,
            user_request=UserRequest(
                UserRequestScope.VARIANT,
                variant_name=variant_name,
                platform_name=config.platform,
                target=UserRequestTarget.FEATURES,
                extra={"gui": config.gui},
            ),
            variant_name=variant_name,
            platform_name=config.platform,
            pipeline=feature_model.pipeline,
        )
        return 0

    @staticmethod
    def select_feature_model(project_slurper: YangaProjectSlurper, platform_name: str | None) -> FeatureModelConfig:
        """The platform's model when a platform is given, else the product model; never one for the other."""
        if platform_name:
            platform = project_slurper.get_platform(platform_name)
            feature_model = platform.feature_model if platform else None
            if not feature_model:
                raise UserNotificationException(f"Platform '{platform_name}' declares no 'feature_model:' block.")
            if not feature_model.pipeline:
                raise UserNotificationException(f"The 'feature_model:' of platform '{platform_name}' ({feature_model.file}) declares no 'pipeline:' to open its editor.")
        else:
            feature_model = project_slurper.feature_model
            if not feature_model:
                raise UserNotificationException("The project declares no 'feature_model:' block.")
            if not feature_model.pipeline:
                raise UserNotificationException(f"The project 'feature_model:' ({feature_model.file}) declares no 'pipeline:' to open its editor.")
        return feature_model

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, FeaturesCommandConfig)
