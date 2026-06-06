import sys
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, TypeVar

import yaml
from mashumaro.exceptions import InvalidFieldValue, MissingField
from py_app_dev.core.config import BaseConfigDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.pipeline import PipelineConfig as GenericPipelineConfig
from pypeline.domain.pipeline import PipelineConfig
from yaml.parser import ParserError
from yaml.scanner import ScannerError

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


# Source-location provenance. See docs/explanation/design-decisions.md
# ("Configuration Provenance") for what it buys and how the pieces fit.

#: Internal wire key the loader's position is injected under. Deliberately not
#: ``location`` so a user's ``location:`` yaml key can't be routed into provenance
#: (it stays an ignored unknown key). The Python field is still named ``location``.
_LOCATION_KEY = "_yanga_location"


@dataclass
class SourceLocation(BaseConfigDictMixin):
    """Where a config element was parsed from (1-based line/column)."""

    file: Path | None = None
    line: int | None = None
    column: int | None = None

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


#: Per-parse stack of locations for error messages only; the top is the element
#: under construction. A stack (not a single slot) is needed so a parent scalar that
#: fails after a nested child still localizes to the parent. ContextVar → thread-safe
#: under the parallel slurp.
_parsing_stack: ContextVar[list[SourceLocation | None] | None] = ContextVar("_yanga_parsing_stack", default=None)


@dataclass
class ConfigElement(BaseConfigDictMixin):
    """Base for every locatable config element; fills ``location`` on parse, strips it on export."""

    # compare=False so equal elements from different files still dedup on merge;
    # kw_only so subclasses keep mandatory positional fields. The wire alias keeps a
    # user's ``location:`` yaml key from hijacking provenance (failure mode A); a
    # subclass redeclaring ``location`` is rejected by __init_subclass__ (mode B).
    location: SourceLocation | None = field(default=None, kw_only=True, compare=False, repr=False, metadata={"alias": _LOCATION_KEY})

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "location" in cls.__dict__.get("__annotations__", {}):
            raise TypeError(f"{cls.__name__} must not declare a 'location' field — it is reserved by ConfigElement for source provenance.")

    @classmethod
    def __pre_deserialize__(cls, d: dict[str, Any]) -> dict[str, Any]:
        # Push for error localization, then lift the loader's position attribute into
        # the aliased key so mashumaro fills the field (matching nested/list natively).
        position = getattr(d, "location", None)
        stack = _parsing_stack.get()
        if stack is not None:
            stack.append(position)  # push None too, to stay balanced with the pop
        if position is not None and _LOCATION_KEY not in d:
            return {**d, _LOCATION_KEY: position.to_dict()}
        return d

    @classmethod
    def __post_deserialize__(cls, obj: Self) -> Self:
        stack = _parsing_stack.get()
        if stack:
            stack.pop()  # constructed OK — drop so the top tracks the live element
        return obj

    def __post_serialize__(self, d: dict[str, Any]) -> dict[str, Any]:
        d.pop("location", None)
        return d


class _PositionedDict(dict[str, Any]):
    """A dict carrying its YAML position as an attribute (never a key, so ``content:`` payloads stay byte-clean)."""

    location: SourceLocation | None = None


def _load_positioned(path: Path) -> Any:
    """Parse YAML, stamping each mapping with its file:line:column."""

    # Function-local loader so the constructor never mutates the global SafeLoader
    # (keeps the parallel slurp safe).
    class _Loader(yaml.SafeLoader):
        pass

    def construct_map(loader: yaml.SafeLoader, node: yaml.MappingNode) -> Any:
        data = _PositionedDict()
        yield data
        data.update(loader.construct_mapping(node))
        data.location = SourceLocation(path, node.start_mark.line + 1, node.start_mark.column + 1)

    _Loader.add_constructor("tag:yaml.org,2002:map", construct_map)
    return yaml.load(path.read_text(), Loader=_Loader)  # noqa: S506 - _Loader subclasses SafeLoader


_T = TypeVar("_T", bound=ConfigElement)


def parse(cls: type[_T], path: Path) -> _T:
    """Load a file into a located config element, localizing both YAML and schema failures."""
    try:
        raw = _load_positioned(path)
    except (ScannerError, ParserError) as e:
        raise UserNotificationException(f"Failed to parse configuration file '{path}'.\n{e}") from e
    token = _parsing_stack.set([])
    try:
        return cls.from_dict(raw)
    except (InvalidFieldValue, MissingField) as e:
        stack = _parsing_stack.get() or []
        location = next((entry for entry in reversed(stack) if entry is not None), None)
        raise UserNotificationException(_format_deserialize_error(path, location, e)) from e
    finally:
        _parsing_stack.reset(token)


def export(element: ConfigElement) -> dict[str, Any]:
    """Serialize a config element back to a dict, with provenance stripped."""
    return element.to_dict()


def _format_deserialize_error(path: Path, location: SourceLocation | None, error: Exception) -> str:
    """Turn a mashumaro schema error into a file:line:col message (file alone when location is unknown)."""
    where = str(location) if location is not None else str(path)
    return f"Failed to parse configuration at {where}: {error}"


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
class MockingConfiguration(ConfigElement):
    enabled: bool | None = None
    strict: bool | None = None
    exclude_symbol_patterns: list[str] | None = None


@dataclass
class TestingConfiguration(ConfigElement):
    #: Component test sources
    sources: list[str] = field(default_factory=list)
    #: Mocking configuration
    mocking: MockingConfiguration | None = None


@dataclass
class DocsConfiguration(ConfigElement):
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
        config = parse(cls, config_file)
        config.file = config_file
        return config
