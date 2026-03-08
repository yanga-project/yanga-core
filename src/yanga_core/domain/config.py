from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

import yaml
from py_app_dev.core.config import BaseConfigDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.pipeline import PipelineConfig as GenericPipelineConfig
from pypeline.domain.pipeline import PipelineConfig
from yaml.parser import ParserError
from yaml.scanner import ScannerError


@dataclass
class ConfigFile(BaseConfigDictMixin):
    """Generic configuration file reference for steps to consume."""

    id: str
    file: Path | None = None
    content: dict[str, Any] | None = None
    # Populated at runtime by collect_configs_by_id; not part of the yaml schema
    source_file: Path | None = None

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
class MockingConfiguration(BaseConfigDictMixin):
    enabled: bool | None = None
    strict: bool | None = None
    exclude_symbol_patterns: list[str] | None = None


@dataclass
class TestingConfiguration(BaseConfigDictMixin):
    #: Component test sources
    sources: list[str] = field(default_factory=list)
    #: Mocking configuration
    mocking: MockingConfiguration | None = None


@dataclass
class DocsConfiguration(BaseConfigDictMixin):
    #: Component documentation sources
    sources: list[str] = field(default_factory=list)
    #: Do not generate documentation for the productive code.
    #  This might be used for integration tests components to avoid generating docs for productive code from other components.
    exclude_productive_code: bool = False


@dataclass
class PlatformConfig(BaseConfigDictMixin):
    #: Platform name
    name: str
    #: Description
    description: str | None = None
    #: Build system generators
    generators: GenericPipelineConfig = field(default_factory=list)
    #: Supported build types
    build_types: list[str] = field(default_factory=list)
    #: Supported targets
    build_targets: list[str] | None = None
    #: Generic config files for steps
    configs: list[ConfigFile] = field(default_factory=list)
    #: Platform specific components
    components: list[str] | None = None
    # This field is intended to keep track of where configuration was loaded from and
    # it is automatically added when configuration is loaded from file
    file: Path | None = None


@dataclass
class VariantPlatformsConfig(BaseConfigDictMixin):
    """Platform specific configuration, used in case the variant needs to defines specific settings for some platforms."""

    #: Components
    components: list[str] = field(default_factory=list)
    #: Generic config files for steps
    configs: list[ConfigFile] = field(default_factory=list)


@dataclass
class VariantConfig(BaseConfigDictMixin):
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
    def from_string(cls, name: str) -> "StringableEnum":
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
class IncludeDirectory(BaseConfigDictMixin):
    #: Include directory path
    path: str
    #: Include directory scope
    scope: IncludeDirectoryScope = field(metadata=stringable_enum_field_metadata(IncludeDirectoryScope))


@dataclass
class ComponentConfig(BaseConfigDictMixin):
    #: Component name
    name: str
    #: Description
    description: str | None = None
    #: Subcomponents - intended for `container` components that can collect other components to ease their management
    components: list[str] = field(default_factory=list)
    #: Component sources
    sources: list[str] = field(default_factory=list)
    #: Component test sources
    test_sources: list[str] = field(default_factory=list)
    #: Testing
    testing: TestingConfiguration | None = None
    #: Documentation sources
    docs_sources: list[str] = field(default_factory=list)
    #: Documentation configuration
    docs: DocsConfiguration | None = None
    #: Component include directories
    include_directories: list[IncludeDirectory] = field(default_factory=list)
    #: Name of the components that this component requires header files from
    required_components: list[str] = field(default_factory=list)
    #: Component alias to be used by other components to refer to this component
    alias: str | None = None
    #: Directory relative to the project root where this component is located
    path: Path | None = None

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
class YangaUserConfig(BaseConfigDictMixin):
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

    # This field is intended to keep track of where the configuration was loaded from and
    # it is automatically added when the configuration is loaded from the file
    file: Path | None = None

    @classmethod
    def from_file(cls, config_file: Path) -> "YangaUserConfig":
        config_dict = cls.parse_to_dict(config_file)
        return cls.from_dict(config_dict)

    @staticmethod
    def parse_to_dict(config_file: Path) -> dict[str, Any]:
        try:
            with open(config_file) as fs:
                config_dict = yaml.safe_load(fs)
                # Add file name to config to keep track of where configuration was loaded from
                config_dict["file"] = config_file
            return config_dict
        except ScannerError as e:
            raise UserNotificationException(f"Failed scanning configuration file '{config_file}'. \nError: {e}") from e
        except ParserError as e:
            raise UserNotificationException(f"Failed parsing configuration file '{config_file}'. \nError: {e}") from e
