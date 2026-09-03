from pathlib import Path

from py_app_dev.core.data_registry import DataRegistry
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from pypeline.domain.config import assemble_pipeline
from pypeline.domain.pipeline import IncludeSpec, PipelineConfig, PipelineConfigIterator

from yanga_core.domain.spl_paths import SPLPaths

from .config import ComponentConfig, ConfigFile, PlatformConfig, VariantConfig, YangaUserConfig
from .config_slurper import YangaConfigSlurper

#: Directories always skipped by the project discovery walk, in addition to any user-configured ``exclude_dirs``.
DEFAULT_EXCLUDE_DIRS: list[str] = [".git", ".github", ".vscode", "build", ".venv"]

__all__ = ["YangaProjectSlurper"]


class YangaProjectSlurper:
    def __init__(self, project_dir: Path, configuration_file_name: str | None = None, exclude_dirs: list[str] | None = None, create_yanga_build_dir: bool = True) -> None:
        self.logger = logger.bind()
        self.project_dir = project_dir
        exclude = exclude_dirs if exclude_dirs else []
        # Merge the exclude directories with the hardcoded ones
        exclude = list({*exclude, *DEFAULT_EXCLUDE_DIRS})
        self.user_configs: list[YangaUserConfig] = YangaConfigSlurper(project_dir=self.project_dir, exclude_dirs=exclude, configuration_file_name=configuration_file_name).slurp()
        self.project_pipeline: PipelineConfig | None = self._find_project_pipeline_config(self.user_configs)
        self.variants: list[VariantConfig] = self._collect_variants(self.user_configs)
        self.platforms: list[PlatformConfig] = self._collect_platforms(self.user_configs)
        self.components: list[ComponentConfig] = self._collect_components(self.user_configs)
        self.create_yanga_build_dir = create_yanga_build_dir

    @property
    def user_config_files(self) -> list[Path]:
        return [user_config.file for user_config in self.user_configs if user_config.file]

    @property
    def project_configs(self) -> list[ConfigFile]:
        """Collect all top level configuration files from the user configurations."""
        configs: list[ConfigFile] = []
        for user_config in self.user_configs:
            configs.extend(user_config.configs)
        return configs

    def get_variant_config(self, variant_name: str) -> VariantConfig:
        variant = next((v for v in self.variants if v.name == variant_name), None)
        if not variant:
            raise UserNotificationException(f"Variant '{variant_name}' not found in the configuration.")

        return variant

    def get_variant_config_file(self, variant_name: str) -> Path | None:
        variant = self.get_variant_config(variant_name)
        spl_paths = SPLPaths(self.project_dir, variant_name, None, None)
        return spl_paths.locate_artifact(variant.features_selection_file, [variant.file]) if variant.features_selection_file else None

    def get_selected_component_names(self, variant_name: str, platform_name: str | None = None) -> list[str]:
        return self._collect_selected_component_names(self.get_variant_config(variant_name), platform_name)

    def register_components(self, data_registry: DataRegistry) -> None:
        """
        Publish every declared component config to the run's data registry.

        The slurper is the *first* producer of component configs; generators publish more
        the same way later in the pipeline. Consumers read the whole population back off
        the registry (registry-as-pool), so the population is never threaded through the
        execution context as a separate field.
        """
        for config in self.components:
            data_registry.insert(config, provider=type(self).__name__)

    def get_pipeline(self, platform_name: str | None) -> PipelineConfig | None:
        """The selected platform's own pipeline if it declares one, else the project pipeline."""
        platform = self.get_platform(platform_name)
        if platform and platform.pipeline:
            return platform.pipeline
        return self.project_pipeline

    def get_platform(self, platform_name: str | None) -> PlatformConfig | None:
        if not platform_name:
            return None
        platform = next((p for p in self.platforms if p.name == platform_name), None)
        if not platform:
            raise UserNotificationException(f"Platform '{platform_name}' not found in the configuration.")
        return platform

    def _collect_selected_component_names(self, variant: VariantConfig, platform_name: str | None = None) -> list[str]:
        """
        Names of the components built for this variant/platform — the build scope.

        The union of the variant's components, the variant's platform-specific components,
        and the platform's own components, validated against the declared components. This is
        selection only: turning configs into ``Component``s and resolving them is the resolver's job.
        """
        if not variant.components:
            raise UserNotificationException(f"Variant '{variant.name}' is empty (no 'components' found).")

        component_names = variant.components.copy()

        # Platform-specific components from the variant's platforms configuration
        if platform_name and variant.platforms and platform_name in variant.platforms:
            component_names.extend(variant.platforms[platform_name].components)

        # Platform-specific components from the platform configuration
        if platform_name:
            platform = next((p for p in self.platforms if p.name == platform_name), None)
            if platform and platform.components:
                component_names.extend(platform.components)

        declared_names = {component.name for component in self.components}
        for component_name in component_names:
            if component_name not in declared_names:
                raise UserNotificationException(f"Component '{component_name}' not found in the configuration.")
        return component_names

    def _collect_components(self, user_configs: list[YangaUserConfig]) -> list[ComponentConfig]:
        components: list[ComponentConfig] = []
        for user_config in user_configs:
            for component in user_config.components:
                existing = next((c for c in components if c.name == component.name), None)
                if existing is not None:
                    raise UserNotificationException(f"Component '{component.name}' is defined in multiple configuration files. See {existing.file} and {user_config.file}")
                # TODO: shall the project slurper be responsible for updating the source file for the configuration?
                component.file = user_config.file
                components.append(component)
        return components

    def _find_project_pipeline_config(self, user_configs: list[YangaUserConfig]) -> PipelineConfig | None:
        declarations: list[tuple[PipelineConfig, Path | None]] = []
        for user_config in user_configs:
            if user_config.pipeline:
                declarations.append((user_config.pipeline, user_config.file))
        if len(declarations) > 1:
            # The files are slurped in parallel, so without this the winner would be whichever parsed first.
            files = ", ".join(sorted(str(file) for _, file in declarations))
            raise UserNotificationException(f"The pipeline is defined in multiple configuration files. Only one may define it. See {files}")
        if not declarations:
            return None
        pipeline, declaring_file = declarations[0]
        return self._assemble_pipeline(pipeline, declaring_file)

    def _assemble_pipeline(self, pipeline: PipelineConfig, declaring_file: Path | None) -> PipelineConfig:
        """Expand the ``include:`` entries; a pipeline built in memory has no file to resolve them against."""
        if not declaring_file:
            return pipeline
        self._resolve_include_paths(pipeline, declaring_file)
        return assemble_pipeline(pipeline, declaring_file)

    def _resolve_include_paths(self, pipeline: PipelineConfig, declaring_file: Path) -> None:
        """
        Rewrite every ``include:`` to an absolute path, in place.

        pypeline looks for a fragment next to the including file. A yanga fragment may also
        live in the project root or in ``platforms/``, so the lookup happens here and pypeline
        receives a path it does not have to resolve again.
        """
        spl_paths = SPLPaths(self.project_dir, None, None, None)
        for _group, steps in PipelineConfigIterator(pipeline):
            for step in steps:
                if step.include is None:
                    continue
                if isinstance(step.include, IncludeSpec):
                    step.include.file = str(spl_paths.locate_artifact(step.include.file, [declaring_file]))
                else:
                    step.include = str(spl_paths.locate_artifact(step.include, [declaring_file]))

    def _collect_variants(self, user_configs: list[YangaUserConfig]) -> list[VariantConfig]:
        variants = []
        for user_config in user_configs:
            for variant in user_config.variants:
                variant.file = user_config.file
                variants.append(variant)
        return variants

    def _collect_platforms(self, user_configs: list[YangaUserConfig]) -> list[PlatformConfig]:
        platforms: list[PlatformConfig] = []
        for user_config in user_configs:
            for platform in user_config.platforms:
                # TODO: shall the project slurper be responsible for updating the source file for the configuration?
                platform.file = user_config.file
                if platform.pipeline:
                    platform.pipeline = self._assemble_pipeline(platform.pipeline, platform.file)
                platforms.append(platform)
        return platforms

    def print_project_info(self) -> None:
        self.logger.info("-" * 80)
        self.logger.info(f"Project directory: {self.project_dir}")
        self.logger.info(f"Parsed {len(self.user_configs)} configuration file(s).")
        self.logger.info(f"Found {len(self.components)} component(s).")
        self.logger.info(f"Found {len(self.variants)} variant(s):")
        for variant in self.variants:
            self.logger.info(f"  - {variant.name}")
        self.logger.info(f"Found {len(self.platforms)} platforms(s):")
        for platform in self.platforms:
            self.logger.info(f"  - {platform.name}")
        if self.project_pipeline:
            self.logger.info("Found pipeline config:")
            self._print_pipeline(self.project_pipeline)
        for platform in self.platforms:
            if platform.pipeline:
                self.logger.info(f"Platform '{platform.name}' pipeline:")
                self._print_pipeline(platform.pipeline)
        self.logger.info("-" * 80)

    def _print_pipeline(self, pipeline: PipelineConfig) -> None:
        for group, step_configs in PipelineConfigIterator(pipeline):
            if group:
                self.logger.info(f"    Group: {group}")
            for step_config in step_configs:
                self.logger.info(f"        {step_config.step}")
