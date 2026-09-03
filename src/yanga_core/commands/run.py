import shutil
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path

from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, time_it
from pypeline.pypeline import PipelineScheduler, PipelineStepsExecutor

from yanga_core.domain.config import PlatformConfig, VariantConfig
from yanga_core.domain.execution_context import ExecutionContext, UserRequest, UserRequestScope
from yanga_core.domain.project_slurper import YangaProjectSlurper
from yanga_core.domain.spl_paths import SPLPaths
from yanga_core.ini import YangaIni

from .base import CommandConfigBase, create_config, prompt_user_to_select_option


@dataclass
class RunCommandConfig(CommandConfigBase):
    platform: str | None = field(
        default=None,
        metadata={"help": "Platform for which to build (see the available platforms in the configuration)."},
    )
    variant_name: str | None = field(
        default=None,
        metadata={"help": "SPL variant name. If none is provided, it will prompt to select one."},
    )
    component_name: str | None = field(default=None, metadata={"help": "Restrict the scope to one specific component."})
    target: str | None = field(default=None, metadata={"help": "Define a specific target to execute."})
    build_type: str | None = field(
        default=None,
        metadata={"help": "Build type to use (e.g., 'Debug', 'Release')."},
    )
    step: str | None = field(
        default=None,
        metadata={"help": "Name of the step to run (as written in the pipeline config)."},
    )
    single: bool = field(
        default=False,
        metadata={
            "help": "If provided, only the provided step will run, without running all previous steps in the pipeline.",
            "action": "store_true",
        },
    )
    print: bool = field(
        default=False,
        metadata={
            "help": "Print the pipeline steps.",
            "action": "store_true",
        },
    )
    force_run: bool = field(
        default=False,
        metadata={
            "help": "Force the execution of a step even if it is not dirty.",
            "action": "store_true",
        },
    )
    not_interactive: bool = field(
        default=False,
        metadata={
            "help": "Run in non-interactive mode (no prompts).",
            "action": "store_true",
        },
    )
    pristine: bool = field(
        default=False,
        metadata={
            "help": "Recursively delete the variant build directory before running. Works even if cmake configure is currently broken (e.g. variant rename, schema change).",
            "action": "store_true",
        },
    )


class RunCommand(Command):
    def __init__(self) -> None:
        super().__init__("run", "Run a yanga pipeline step (and all previous steps if necessary).")
        self.logger = logger.bind()

    @time_it("Run")
    def run(self, args: Namespace) -> int:
        self.logger.debug(f"Running {self.name} with args {args}")
        self.do_run(create_config(RunCommandConfig, args))
        return 0

    def do_run(self, config: RunCommandConfig) -> int:
        ini_config = YangaIni.from_toml_or_ini(config.project_dir / "yanga.ini", config.project_dir / "pyproject.toml")
        if config.pristine:
            self._run_pristine(config, ini_config)
        project_slurper = self.create_project_slurper(config.project_dir, ini_config)
        if config.print:
            project_slurper.print_project_info()
            return 0
        if config.not_interactive:
            variant_name = config.variant_name
            platform_name = config.platform
            build_type = config.build_type
            # In case there is a platform specified but no build type, try to get the default one
            if platform_name and not build_type:
                build_type = self.determine_build_type(config.build_type, platform_name, project_slurper, config.not_interactive)
        else:
            variant_name = self.determine_variant_name(config.variant_name, project_slurper.variants)
            platform_name = self.determine_platform_name(config.platform, project_slurper.platforms)
            build_type = self.determine_build_type(config.build_type, platform_name, project_slurper, config.not_interactive)
        user_request = UserRequest(
            scope=(UserRequestScope.COMPONENT if config.component_name else UserRequestScope.VARIANT),
            variant_name=variant_name,
            component_name=config.component_name,
            target=config.target,
            build_type=build_type,
        )
        self.execute_pipeline_steps(
            project_dir=config.project_dir,
            project_slurper=project_slurper,
            user_request=user_request,
            variant_name=variant_name,
            platform_name=platform_name,
            step=config.step,
            single=config.single,
            force_run=config.force_run,
        )
        return 0

    @staticmethod
    def _run_pristine(config: RunCommandConfig, ini_config: YangaIni) -> None:
        spl_paths = SPLPaths(config.project_dir, config.variant_name, config.platform, config.build_type, create_yanga_build_dir=ini_config.create_yanga_build_dir)
        target_dir = spl_paths.variant_build_dir.resolve(strict=False)
        yanga_build_root = spl_paths.build_dir.resolve(strict=False)
        variants_root = spl_paths.variants_build_root.resolve(strict=False)
        # A scoped wipe must stay strictly inside 'variants/'; a name like '..' would otherwise
        # collapse onto the build root and wipe the SPL build as well.
        is_scoped = any([config.variant_name, config.platform, config.build_type])
        if is_scoped and (target_dir == variants_root or not target_dir.is_relative_to(variants_root)):
            raise UserNotificationException(f"Refusing to wipe {target_dir}: it escapes yanga build root {yanga_build_root}.")
        if not target_dir.exists():
            return
        try:
            shutil.rmtree(target_dir)
        except OSError as e:
            raise UserNotificationException(f"Failed to wipe {target_dir}: {e}") from e

    @staticmethod
    def create_project_slurper(project_dir: Path, ini_config: YangaIni | None = None) -> YangaProjectSlurper:
        if ini_config is None:
            ini_config = YangaIni.from_toml_or_ini(project_dir / "yanga.ini", project_dir / "pyproject.toml")
        return YangaProjectSlurper(project_dir, ini_config.configuration_file_name, create_yanga_build_dir=ini_config.create_yanga_build_dir, exclude_dirs=ini_config.exclude_dirs)

    @staticmethod
    def execute_pipeline_steps(
        project_dir: Path,
        project_slurper: YangaProjectSlurper,
        user_request: UserRequest,
        variant_name: str | None = None,
        platform_name: str | None = None,
        step: str | None = None,
        force_run: bool = False,
        single: bool = False,
    ) -> None:
        pipeline = project_slurper.get_pipeline(platform_name)
        if not pipeline:
            raise UserNotificationException("No pipeline found in the configuration.")
        # Schedule the steps to run
        steps_references = PipelineScheduler[ExecutionContext](pipeline, project_dir).get_steps_to_run([step] if step else None, single)
        if not steps_references:
            if step:
                raise UserNotificationException(f"Step '{step}' not found in the pipeline.")
            logger.info("No steps to run.")
            return
        execution_context = ExecutionContext(
            project_root_dir=project_dir,
            variant_name=variant_name,
            user_request=user_request,
            selected_component_names=(project_slurper.get_selected_component_names(variant_name, platform_name) if variant_name else []),
            user_config_files=project_slurper.user_config_files,
            features_selection_file=(project_slurper.get_variant_config_file(variant_name) if variant_name else None),
            platform=project_slurper.get_platform(platform_name),
            variant=(project_slurper.get_variant_config(variant_name) if variant_name else None),
            project_configs=project_slurper.project_configs,
            create_yanga_build_dir=project_slurper.create_yanga_build_dir,
        )
        # Publish the declared component configs to the run's registry (registry-as-pool);
        # generators publish more during the pipeline, and the resolver reads them all back.
        if variant_name:
            project_slurper.register_components(execution_context.data_registry)
        PipelineStepsExecutor[ExecutionContext](
            execution_context,
            steps_references,
            force_run,
        ).run()

    def determine_variant_name(self, variant_name: str | None, variant_configs: list[VariantConfig]) -> str | None:
        selected_variant_name: str | None
        if not variant_name:
            if len(variant_configs) == 1:
                selected_variant_name = variant_configs[0].name
                self.logger.info(f"Only one variant found. Using '{selected_variant_name}'.")
            else:
                selected_variant_name = prompt_user_to_select_option([variant.name for variant in variant_configs], "Select variant: ")
        else:
            selected_variant_name = variant_name
        if not selected_variant_name:
            self.logger.warning("No variant selected. This might cause some steps to fail.")
        return selected_variant_name

    def determine_platform_name(self, platform_name: str | None, platform_configs: list[PlatformConfig]) -> str | None:
        selected_platform_name: str | None
        if not platform_name:
            if len(platform_configs) == 1:
                selected_platform_name = platform_configs[0].name
                self.logger.info(f"Only one platform found. Using '{selected_platform_name}'.")
            else:
                selected_platform_name = prompt_user_to_select_option(
                    [platform.name for platform in platform_configs],
                    "Select platform: ",
                )
        else:
            selected_platform_name = platform_name
        if not selected_platform_name:
            self.logger.warning("No platform selected. This might cause some steps to fail.")
        return selected_platform_name

    def determine_build_type(
        self,
        build_type: str | None,
        platform_name: str | None,
        project_slurper: YangaProjectSlurper,
        not_interactive: bool,
    ) -> str | None:
        selected_build_type: str | None
        platform = project_slurper.get_platform(platform_name) if platform_name else None
        available_build_types = platform.build_types if platform and platform.build_types else []
        if not build_type:
            if len(available_build_types) == 1:
                selected_build_type = available_build_types[0]
                self.logger.info(f"Only one build type found. Using '{selected_build_type}'.")
            elif len(available_build_types) > 1:
                if not_interactive:
                    self.logger.warning(f"Multiple build types available for '{platform_name}' but none specified. Select first build type by default.")
                    selected_build_type = available_build_types[0]
                else:
                    selected_build_type = prompt_user_to_select_option(
                        available_build_types,
                        "Select build type: ",
                    )
            else:
                selected_build_type = None
        else:
            selected_build_type = build_type
        if not selected_build_type and available_build_types:
            self.logger.warning("No build type selected. This might cause some steps to fail.")
        return selected_build_type

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, RunCommandConfig)
