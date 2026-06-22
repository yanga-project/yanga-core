from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from pypeline.domain.artifacts import ProjectArtifactsLocator
from pypeline.domain.execution_context import ExecutionContext as _ExecutionContext
from pypeline.domain.external_project import ExternalProject

from .component_resolver import ComponentResolver
from .components import Component
from .config import ComponentConfig, ConfigFile, PlatformConfig, VariantConfig
from .spl_paths import SPLPaths


class UserRequestTarget(Enum):
    NONE = auto()
    ALL = auto()
    BUILD = auto()
    COMPILE = auto()
    CLEAN = auto()
    TEST = auto()
    COVERAGE = auto()
    MOCKUP = auto()
    LINT = auto()
    DOCS = auto()
    REPORT = auto()
    #: These are all results relevant for reports generation (e.g., test results, coverage results, lint results, etc.)
    RESULTS = auto()

    def __str__(self) -> str:
        return self.name.lower()


class UserRequestScope(Enum):
    VARIANT = auto()
    COMPONENT = auto()


@dataclass(frozen=True, order=True)
class UserRequest:
    scope: UserRequestScope
    variant_name: str | None = None
    component_name: str | None = None
    target: str | UserRequestTarget | None = None
    build_type: str | None = None

    @property
    def target_name(self) -> str:
        target = str(self.target if self.target else UserRequestTarget.ALL)
        if self.component_name:
            return f"{self.component_name}_{target}"
        return target


class UserVariantRequest(UserRequest):
    def __init__(
        self,
        variant_name: str | None,
        target: str | UserRequestTarget | None = None,
        build_type: str | None = None,
    ) -> None:
        super().__init__(UserRequestScope.VARIANT, variant_name, None, target=target, build_type=build_type)


@dataclass
class ExecutionContext(_ExecutionContext):
    def __init__(
        self,
        project_root_dir: Path,
        user_request: UserRequest,
        variant_name: str | None = None,
        selected_component_names: list[str] | None = None,
        user_config_files: list[Path] | None = None,
        features_selection_file: Path | None = None,
        platform: PlatformConfig | None = None,
        variant: VariantConfig | None = None,
        project_configs: list[ConfigFile] | None = None,
        create_yanga_build_dir: bool = True,
    ) -> None:
        super().__init__(project_root_dir)
        self.user_request = user_request
        self.variant_name = variant_name
        #: The build scope: names of the components this variant/platform actually builds.
        #: The component *population* is not stored here — it lives on the data registry
        #: (registry-as-pool), where the slurper and any generators publish ``ComponentConfig``s.
        self._selected_component_names = selected_component_names if selected_component_names else []
        self.user_config_files = user_config_files if user_config_files else []
        self.features_selection_file = features_selection_file
        self.platform = platform
        self.variant = variant
        self.project_configs: list[ConfigFile] = project_configs if project_configs else []
        self.create_yanga_build_dir = create_yanga_build_dir
        #: Run-scoped resolver, built once on first access (the freeze point) and shared.
        self._component_resolver: ComponentResolver | None = None

    @property
    def spl_paths(self) -> SPLPaths:
        return SPLPaths(
            self.project_root_dir,
            self.variant_name,
            self.platform.name if self.platform else None,
            self.user_request.build_type,
            create_yanga_build_dir=self.create_yanga_build_dir,
        )

    @property
    def components(self) -> list[Component]:
        """The components built for this variant/platform (delegates to the resolver)."""
        return self.component_resolver.selected_components

    @property
    def component_resolver(self) -> ComponentResolver:
        """
        Run-scoped, shared component resolver — the single component authority.

        Built once on first access (the freeze point) and memoised, so every consumer
        resolves each component once. The population is read off the data registry, where
        the slurper and any generators have published their ``ComponentConfig``s, then
        so a component generated mid-pipeline is indistinguishable from a declared one. All
        component-producing steps must run before first access.
        """
        if self._component_resolver is None:
            configs = self.data_registry.find_data(ComponentConfig)
            external_projects = {project.name: project.path for project in self.data_registry.find_data(ExternalProject)}
            self._component_resolver = ComponentResolver(configs, self._selected_component_names, self.spl_paths, external_projects)
        return self._component_resolver

    def create_artifacts_locator(self) -> ProjectArtifactsLocator:
        return self.spl_paths
