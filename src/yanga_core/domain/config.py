import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

import yaml
from py_app_dev.core.config import ConfigElement, parse_config_element
from py_app_dev.core.pipeline import PipelineConfig as GenericPipelineConfig
from pypeline.domain.pipeline import PipelineConfig

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass
class ConfigFile(ConfigElement):
    """Generic configuration file reference for steps to consume."""

    id: str
    file: Path | None = None
    content: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.file is None and self.content is None:
            raise ValueError(f"ConfigFile '{self.id}' must have either 'file' or 'content'")


@dataclass
class VarsConfig:
    """Generic configuration variables to be added as `configs` with id `vars`."""

    vars: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VarsConfig":
        """Create from dict - treats the entire dict as vars."""
        return cls(vars=data)

    @classmethod
    def from_file(cls, path: Path) -> "VarsConfig":
        """Load from YAML file - treats file content as vars dict."""
        with open(path) as fs:
            data = yaml.safe_load(fs) or {}
        return cls(vars=data)


@dataclass
class MockingConfig(ConfigElement):
    enabled: bool | None = None
    strict: bool | None = None
    exclude_symbol_patterns: list[str] | None = None


@dataclass
class TestingConfig(ConfigElement):
    #: Component test sources
    sources: list[str] = field(default_factory=list)
    #: Mocking configuration
    mocking: MockingConfig | None = None


@dataclass
class DocsConfig(ConfigElement):
    #: Component documentation sources
    sources: list[str] = field(default_factory=list)
    #: Do not generate documentation for the productive code.
    #  This might be used for integration tests components to avoid generating docs for productive code from other components.
    exclude_productive_code: bool = False


@dataclass
class BuildTargets(ConfigElement):
    """
    Scoped build targets for a platform.

    `generic` targets apply to both variant and component scopes; `variant` and
    `component` lists carry scope-only targets. Effective sets are computed by
    merging `generic` with the scope-specific list, deduplicated and order-preserving.
    """

    generic: list[str] = field(default_factory=list)
    variant: list[str] = field(default_factory=list)
    component: list[str] = field(default_factory=list)

    @property
    def variant_targets(self) -> list[str]:
        return _dedup_preserve_order(self.generic, self.variant)

    @property
    def component_targets(self) -> list[str]:
        return _dedup_preserve_order(self.generic, self.component)


def _dedup_preserve_order(*lists: list[str]) -> list[str]:
    return list(dict.fromkeys(item for lst in lists for item in lst))


@dataclass
class PlatformConfig(ConfigElement):
    #: Platform name
    name: str
    #: Description
    description: str | None = None
    #: Build system generators
    generators: GenericPipelineConfig = field(default_factory=list)
    #: Pipeline run for this platform instead of the project one
    pipeline: PipelineConfig | None = None
    #: Supported build types
    build_types: list[str] = field(default_factory=list)
    #: Supported targets. Either a flat list (applies to both scopes) or a
    #: ``BuildTargets`` object that splits targets between variant and component.
    #: Order is BuildTargets first so mashumaro picks the dataclass for dict input
    #: (otherwise `list[str]` would match the dict's keys).
    build_targets: BuildTargets | list[str] | None = None
    #: Generic config files for steps
    configs: list[ConfigFile] = field(default_factory=list)
    #: Platform specific components
    components: list[str] | None = None
    # This field is intended to keep track of where configuration was loaded from and
    # it is automatically added when configuration is loaded from file
    file: Path | None = None

    @property
    def variant_build_targets(self) -> list[str]:
        return self._scoped_targets("variant")

    @property
    def component_build_targets(self) -> list[str]:
        return self._scoped_targets("component")

    def _scoped_targets(self, scope: str) -> list[str]:
        if self.build_targets is None:
            return []
        if isinstance(self.build_targets, BuildTargets):
            return self.build_targets.variant_targets if scope == "variant" else self.build_targets.component_targets
        return list(self.build_targets)


@dataclass
class VariantPlatformsConfig(ConfigElement):
    """Platform specific configuration, used in case the variant needs to defines specific settings for some platforms."""

    #: Components
    components: list[str] = field(default_factory=list)
    #: Generic config files for steps
    configs: list[ConfigFile] = field(default_factory=list)


@dataclass
class VariantConfig(ConfigElement):
    #: Variant name
    name: str
    #: Description
    description: str | None = None
    #: Components
    components: list[str] = field(default_factory=list)
    #: Platform specific configuration, used in case the variant needs to defines specific settings for some platforms
    platforms: dict[str, VariantPlatformsConfig] | None = None
    #: Configuration
    features_selection_file: str | None = None
    #: Generic config files for steps
    configs: list[ConfigFile] = field(default_factory=list)
    # This field is intended to keep track of where configuration was loaded from and
    # it is automatically added when configuration is loaded from file
    file: Path | None = None


class StringableEnum(Enum):
    @classmethod
    def from_string(cls, name: str) -> Self:
        return getattr(cls, str(name).upper())

    def to_string(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.to_string()


def stringable_enum_field_metadata(
    enum_type: type[StringableEnum],
    alias: str | None = None,
) -> dict[str, Any]:
    """Generates metadata for dataclass fields that handle stringable enum types."""
    metadata: dict[str, Callable[[Any], Any]] = {
        "deserialize": lambda type_str: enum_type.from_string(type_str) if type_str else None,
        "serialize": lambda type_obj: type_obj.to_string() if type_obj else None,
    }
    if alias:
        metadata["alias"] = alias  # type: ignore
    return metadata


class IncludeDirectoryScope(StringableEnum):
    PUBLIC = auto()
    PRIVATE = auto()


@dataclass
class IncludeDirectory(ConfigElement):
    #: Include directory path
    path: str
    #: Include directory scope
    scope: IncludeDirectoryScope = field(metadata=stringable_enum_field_metadata(IncludeDirectoryScope))


@dataclass
class ComponentConfig(ConfigElement):
    #: Component name
    name: str
    #: Description
    description: str | None = None
    #: Subcomponents - intended for `container` components that can collect other components to ease their management
    subcomponents: list[str] = field(default_factory=list)
    #: Component sources
    sources: list[str] = field(default_factory=list)
    #: Component test sources
    test_sources: list[str] = field(default_factory=list)
    #: Testing
    testing: TestingConfig | None = None
    #: Documentation sources
    docs_sources: list[str] = field(default_factory=list)
    #: Documentation configuration
    docs: DocsConfig | None = None
    #: Component include directories
    include_directories: list[IncludeDirectory] = field(default_factory=list)
    #: Name of the components that this component requires header files from
    required_components: list[str] = field(default_factory=list)
    #: Component alias to be used by other components to refer to this component
    alias: str | None = None
    #: Directory relative to the project root where this component is located
    path: Path | None = None
    #: Name of an ``ExternalProject`` (e.g. a west dependency) this component lives in.
    #: When set, ``path`` is relative to that project's resolved install location
    #: instead of the project root, so the workspace/install layout stays out of the YAML.
    external: str | None = None

    # This field is intended to keep track of where configuration was loaded from and
    # it is automatically added when configuration is loaded from file
    file: Path | None = None

    @property
    def private_include_directories(self) -> list[str]:
        return [d.path for d in self.include_directories if d.scope == IncludeDirectoryScope.PRIVATE]

    @property
    def public_include_directories(self) -> list[str]:
        return [d.path for d in self.include_directories if d.scope == IncludeDirectoryScope.PUBLIC]


@dataclass
class YangaUserConfig(ConfigElement):
    #: Pipeline steps to execute
    pipeline: PipelineConfig | None = None
    #: Supported platforms to build for
    platforms: list[PlatformConfig] = field(default_factory=list)
    #: Software product variants
    variants: list[VariantConfig] = field(default_factory=list)
    #: Software components that can be used to create variants
    components: list[ComponentConfig] = field(default_factory=list)
    #: Generic config files for steps
    configs: list[ConfigFile] = field(default_factory=list)

    # Convenience reference to the loaded file (equals ``location.file``); kept for
    # the many readers that expect ``.file`` on a user config.
    file: Path | None = None

    @classmethod
    def from_file(cls, config_file: Path) -> "YangaUserConfig":
        config = parse_config_element(cls, config_file)
        config.file = config_file
        return config
