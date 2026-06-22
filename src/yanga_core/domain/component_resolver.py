from collections import OrderedDict
from pathlib import Path

from py_app_dev.core.exceptions import UserNotificationException

from .components import Component
from .config import ComponentConfig, IncludeDirectoryScope
from .spl_paths import SPLPaths


def resolve_include_directories(components: list[Component]) -> list[Path]:
    """
    Aggregate the include directories of the given resolved components, de-duplicated.

    Each resolved ``Component`` already carries its transitive include directories (own
    private plus inherited public plus located-source parents), resolved once by
    ``ComponentResolver``. This just flattens them across the components.
    """
    dirs: list[Path] = []
    for component in components:
        dirs.extend(component.include_directories)
    return list(dict.fromkeys(dirs))


def declared_location(config: ComponentConfig) -> Path:
    """
    The single rule for *where* a component lives, relative to its anchor.

    Its declared ``path`` (relative to the project root, or — when ``external`` — to the
    installed project), or, for a path-less in-tree component, the directory of the config
    file that declares it. ``ComponentResolver`` anchors this to an absolute root; other
    readers (e.g. ``yanga info``) reuse the rule for display rather than re-deriving it.
    """
    if config.path:
        return config.path
    if not config.external and config.file:
        return config.file.parent
    return Path()


def _scoped_include_directories(config: ComponentConfig, scope: IncludeDirectoryScope) -> list[str]:
    return [directory.path for directory in config.include_directories if directory.scope == scope]


def _declared_test_sources(config: ComponentConfig) -> list[str]:
    sources = list(config.testing.sources) if config.testing and config.testing.sources else []
    sources.extend(config.test_sources)
    return sources


def _declared_docs_sources(config: ComponentConfig) -> list[str]:
    sources = list(config.docs.sources) if config.docs and config.docs.sources else []
    sources.extend(config.docs_sources)
    return sources


def _build_config_lookup(configs: list[ComponentConfig]) -> dict[str, ComponentConfig]:
    lookup: dict[str, ComponentConfig] = {}
    for config in configs:
        if config.name in lookup:
            raise UserNotificationException(f"Duplicate component name '{config.name}' found.")
        lookup[config.name] = config
        if config.alias:
            if config.alias in lookup:
                existing = lookup[config.alias]
                raise UserNotificationException(f"Duplicate alias '{config.alias}' found: used by both '{existing.name}' and '{config.name}'.")
            lookup[config.alias] = config
    return lookup


class ComponentResolver:
    """
    The single component authority.

    Turns ``ComponentConfig``s into fully-resolved ``Component``s — absolute root, located
    source files, and the transitive include-directory set — using its internal config pool
    and the install context. Each component is resolved once and memoised; consumers read
    the resolved ``Component``'s fields directly and never call back here.

    Lookups go to the **selected** components first (by name and alias, so the platform's
    alias choice wins), then fall back to the full declared population by name only, so a
    required component that is declared but not selected (e.g. an interface component) still
    resolves. The name-only fallback lets the population carry several components sharing one
    alias (the alias-per-platform pattern) without collision.
    """

    def __init__(self, configs: list[ComponentConfig], selected_names: list[str], spl_paths: SPLPaths, external_projects: dict[str, Path] | None = None) -> None:
        self._spl_paths = spl_paths
        #: Resolved install location of each ``ExternalProject`` (name -> path), snapshotted
        #: when the resolver is built (the run's freeze point).
        self._external_projects = external_projects if external_projects else {}
        #: The config pool: the full declared population, indexed by name.
        self._configs_by_name = {config.name: config for config in configs}
        #: Build scope, in selection order (names present in the population).
        self._selected_names = [name for name in selected_names if name in self._configs_by_name]
        #: Selected scope indexed by name and alias (the build's alias choice wins).
        self._selected_lookup = _build_config_lookup([self._configs_by_name[name] for name in self._selected_names])
        #: Memoised resolved components, roots, and public-include walks, keyed by name.
        self._components: dict[str, Component] = {}
        self._roots: dict[str, Path] = {}
        self._public_includes: dict[str, list[Path]] = {}

    @property
    def selected_components(self) -> list[Component]:
        """The resolved components built for this variant/platform, in selection order."""
        return [self._component(name) for name in self._selected_names]

    def _component(self, name: str) -> Component:
        config = self._lookup_config(name)
        if config.name not in self._components:
            self._components[config.name] = self._resolve(config)
        return self._components[config.name]

    def _resolve(self, config: ComponentConfig) -> Component:
        root = self._root_for(config)
        sources = [root / source for source in config.sources]
        component = Component(
            name=config.name,
            path=root,
            sources=sources,
            test_sources=[root / source for source in _declared_test_sources(config)],
            docs_sources=[root / source for source in _declared_docs_sources(config)],
            include_directories=self._resolve_include_directories(config, root, sources),
            testing=config.testing,
            docs=config.docs,
            required_components=config.required_components,
            alias=config.alias,
            description=config.description,
        )
        for subcomponent_name in config.subcomponents:
            subcomponent = self._component(subcomponent_name)
            subcomponent.is_subcomponent = True
            component.subcomponents.append(subcomponent)
        return component

    def _resolve_include_directories(self, config: ComponentConfig, root: Path, located_sources: list[Path]) -> list[Path]:
        dirs = [root.joinpath(inc) for inc in _scoped_include_directories(config, IncludeDirectoryScope.PRIVATE)]
        dirs += self._collect_public_includes(config.name, [])
        dirs += [source.parent for source in located_sources]
        return list(OrderedDict.fromkeys(dirs))

    def _collect_public_includes(self, name: str, dependency_path: list[str]) -> list[Path]:
        config = self._lookup_config(name)
        if config.name in self._public_includes:
            return self._public_includes[config.name]
        if config.name in dependency_path:
            chain = " -> ".join([*dependency_path[dependency_path.index(config.name) :], config.name])
            raise UserNotificationException(f"Circular dependency detected: {chain}")
        root = self._root_for(config)
        includes = [root.joinpath(inc) for inc in _scoped_include_directories(config, IncludeDirectoryScope.PUBLIC)]
        for dep_name in config.required_components:
            includes.extend(self._collect_public_includes(dep_name, [*dependency_path, config.name]))
        deduped = list(OrderedDict.fromkeys(includes))
        self._public_includes[config.name] = deduped
        return deduped

    def _root_for(self, config: ComponentConfig) -> Path:
        """
        Resolve a config's absolute root — the single place a path is resolved, memoised.

        ``declared_location`` gives the path relative to the anchor; this anchors it: under
        the project root for an in-tree component, or under the installed ``ExternalProject``
        for an ``external`` one (failing fast, naming the project, if it is not yet in the
        registry — like the GTest generator).
        """
        if config.name in self._roots:
            return self._roots[config.name]
        path = declared_location(config)
        if config.external:
            base = self._external_projects.get(config.external)
            if base is None:
                raise UserNotificationException(
                    f"Component '{config.name}' requires external project '{config.external}', which is not in the data registry (no matching ExternalProject was installed)."
                )
            root = base / path
        else:
            root = self._spl_paths.project_root_dir / path
        self._roots[config.name] = root
        return root

    def _lookup_config(self, name: str) -> ComponentConfig:
        config = self._selected_lookup.get(name) or self._configs_by_name.get(name)
        if config is None:
            raise UserNotificationException(f"Component '{name}' not found in the declared components.")
        return config
