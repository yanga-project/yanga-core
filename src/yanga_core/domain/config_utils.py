import sys
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast

from yanga_core.domain.config import ConfigFile
from yanga_core.domain.execution_context import ExecutionContext

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class ConfigPrototype(Protocol):
    """Protocol for config classes that support from_dict and from_file."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self: ...

    @classmethod
    def from_file(cls, path: Path) -> Self: ...


T = TypeVar("T", bound=ConfigPrototype)


def collect_configs_by_id(context: ExecutionContext, config_id: str) -> list[ConfigFile]:
    """
    Collect configs matching id. Order: project → variant → platform → variant-platform.

    Each ConfigFile already carries its ``location`` from when its yanga.yaml was
    parsed, so no source-file stamping is needed here.
    """
    configs: list[ConfigFile] = []

    # 1. Project configs
    configs.extend(cfg for cfg in context.project_configs if cfg.id == config_id)

    # 2. Variant configs
    if context.variant:
        configs.extend(cfg for cfg in context.variant.configs if cfg.id == config_id)

    # 3. Platform configs
    if context.platform:
        configs.extend(cfg for cfg in context.platform.configs if cfg.id == config_id)

    # 4. Variant-Platform configs
    if context.variant and context.platform and context.variant.platforms:
        if context.platform.name in context.variant.platforms:
            vp_config = context.variant.platforms[context.platform.name]
            configs.extend(cfg for cfg in vp_config.configs if cfg.id == config_id)

    return configs


def parse_config(config: ConfigFile, prototype: type[T], base_path: Path | None = None) -> T:
    """
    Parse ConfigFile using prototype's from_dict or from_file.

    File resolution order for relative paths:
    1. Relative to the declaring yanga.yaml (``location.file.parent``), if known and the file exists there
    2. Relative to base_path (typically project root), as fallback
    """
    if config.content:
        return cast(T, prototype.from_dict(config.content))
    if config.file:
        decl_dir = config.location.file.parent if config.location and config.location.file else None
        if decl_dir and not Path(config.file).is_absolute():
            candidate = decl_dir / config.file
            if candidate.exists():
                return cast(T, prototype.from_file(candidate))
        file_path = base_path / config.file if base_path else config.file
        return cast(T, prototype.from_file(file_path))
    raise ValueError(f"ConfigFile '{config.id}' has neither file nor content")
