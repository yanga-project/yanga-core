"""
Typed schema for the ``yanga info`` JSON output.

The version is a ``"major.minor"`` string. Major bumps signal breaking
structural changes; minor bumps signal backwards-compatible additions
(new fields, new enum values).
"""

from dataclasses import dataclass, field
from pathlib import Path

from py_app_dev.core.config import BaseConfigDictMixin, BaseConfigJSONMixin

from yanga_core.domain.config import BuildTargets, PlatformConfig
from yanga_core.domain.project_slurper import DEFAULT_EXCLUDE_DIRS, ComponentFactory, YangaProjectSlurper
from yanga_core.ini import YangaIni

SCHEMA_VERSION = "1.1"
DEFAULT_CONFIGURATION_FILE_NAME = "yanga.yaml"
TOP_LEVEL_CONFIG_FILE_NAMES = ("yanga.ini", "pyproject.toml")


@dataclass
class InfoDiagnostic(BaseConfigDictMixin):
    severity: str
    message: str
    code: str | None = None
    file: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass
class InfoComponent(BaseConfigDictMixin):
    name: str
    path: str


@dataclass
class InfoPlatform(BaseConfigDictMixin):
    name: str
    build_types: list[str] = field(default_factory=list)
    #: Scoped build targets. ``generic`` applies to both variant and component
    #: scopes; ``variant`` and ``component`` are scope-only. Always emitted as a
    #: dict with all three keys (empty lists when unset).
    build_targets: BuildTargets = field(default_factory=BuildTargets)
    components: list[str] = field(default_factory=list)


@dataclass
class InfoVariant(BaseConfigDictMixin):
    name: str
    components: list[str] = field(default_factory=list)
    platform_components: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class InfoProject(BaseConfigJSONMixin):
    schema_version: str
    project_dir: str
    config_files: list[str] = field(default_factory=list)
    watch_patterns: list[str] = field(default_factory=list)
    ignore_patterns: list[str] = field(default_factory=list)
    platforms: list[InfoPlatform] = field(default_factory=list)
    variants: list[InfoVariant] = field(default_factory=list)
    components: list[InfoComponent] = field(default_factory=list)
    diagnostics: list[InfoDiagnostic] = field(default_factory=list)

    def find_platform(self, name: str | None) -> InfoPlatform | None:
        if not name:
            return None
        return next((p for p in self.platforms if p.name == name), None)

    def find_variant(self, name: str | None) -> InfoVariant | None:
        if not name:
            return None
        return next((v for v in self.variants if v.name == name), None)

    def get_effective_variant_components(self, variant_name: str, platform_name: str | None) -> list[str]:
        """
        Effective component name list for a (variant, platform) pair.

        Merges (in order) variant base components, the variant's platform overlay,
        and the platform's own component list. Deduplicated, order-preserving.
        """
        variant = self.find_variant(variant_name)
        if variant is None:
            return []
        sources: list[list[str]] = [variant.components]
        if platform_name:
            sources.append(variant.platform_components.get(platform_name, []))
            platform = self.find_platform(platform_name)
            if platform is not None:
                sources.append(platform.components)
        seen: set[str] = set()
        out: list[str] = []
        for src in sources:
            for name in src:
                if name not in seen:
                    seen.add(name)
                    out.append(name)
        return out


def build_info_project(
    project_dir: Path,
    slurper: YangaProjectSlurper,
    ini: YangaIni,
    diagnostics: list[InfoDiagnostic] | None = None,
) -> InfoProject:
    configuration_file_name = ini.configuration_file_name or DEFAULT_CONFIGURATION_FILE_NAME
    return InfoProject(
        schema_version=SCHEMA_VERSION,
        project_dir=str(project_dir.resolve()),
        config_files=_config_files(project_dir, slurper.user_config_files),
        watch_patterns=[f"**/{configuration_file_name}"],
        ignore_patterns=_ignore_patterns(ini.exclude_dirs),
        platforms=_platforms(slurper),
        variants=_variants(slurper),
        components=_components(project_dir, slurper),
        diagnostics=list(diagnostics) if diagnostics else [],
    )


def _config_files(project_dir: Path, user_config_files: list[Path]) -> list[str]:
    paths: list[str] = []
    for name in TOP_LEVEL_CONFIG_FILE_NAMES:
        if (project_dir / name).is_file():
            paths.append(name)
    paths.extend(_to_relative_posix(project_dir, p) for p in user_config_files)
    seen: set[str] = set()
    deduped: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def _ignore_patterns(user_exclude_dirs: list[str]) -> list[str]:
    merged = sorted({*DEFAULT_EXCLUDE_DIRS, *(user_exclude_dirs or [])})
    return [f"{d.rstrip('/')}/**" for d in merged]


def _platforms(slurper: YangaProjectSlurper) -> list[InfoPlatform]:
    return [
        InfoPlatform(
            name=p.name,
            build_types=list(p.build_types or []),
            build_targets=_normalize_build_targets(p),
            components=list(p.components or []),
        )
        for p in slurper.platforms
    ]


def _normalize_build_targets(p: PlatformConfig) -> BuildTargets:
    """
    Bring both config forms onto the same wire shape.

    Bare-list configs (`build_targets: [a, b, c]`) preserve their original
    "applies to both scopes" semantics by mapping into `generic`.
    """
    if p.build_targets is None:
        return BuildTargets()
    if isinstance(p.build_targets, BuildTargets):
        return BuildTargets(
            generic=list(p.build_targets.generic),
            variant=list(p.build_targets.variant),
            component=list(p.build_targets.component),
        )
    return BuildTargets(generic=list(p.build_targets))


def _variants(slurper: YangaProjectSlurper) -> list[InfoVariant]:
    out: list[InfoVariant] = []
    for variant in slurper.variants:
        platform_components: dict[str, list[str]] = {}
        if variant.platforms:
            for platform_name, overlay in variant.platforms.items():
                platform_components[platform_name] = list(overlay.components or [])
        out.append(
            InfoVariant(
                name=variant.name,
                components=list(variant.components or []),
                platform_components=platform_components,
            )
        )
    return out


def _components(project_dir: Path, slurper: YangaProjectSlurper) -> list[InfoComponent]:
    factory = ComponentFactory(project_dir)
    return [
        InfoComponent(
            name=cfg.name,
            path=_to_relative_posix(project_dir, factory.create(cfg).path),
        )
        for cfg in slurper.components_configs_pool.values()
    ]


def _to_relative_posix(project_dir: Path, path: Path) -> str:
    resolved_root = project_dir.resolve()
    resolved = path.resolve() if path.is_absolute() else (project_dir / path).resolve()
    try:
        return resolved.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved.as_posix()
