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


def _with_subcomponents(component: Component) -> list[Component]:
    return [component, *(nested for subcomponent in component.subcomponents for nested in _with_subcomponents(subcomponent))]


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
        directly_selected = [name for name in selected_names if name in self._configs_by_name]
        #: Selected scope indexed by name and alias (the build's alias choice wins). Built from
        #: the direct selection first, because container expansion resolves aliases against it.
        self._selected_lookup = _build_config_lookup([self._configs_by_name[name] for name in directly_selected])
        #: Build scope, in selection order, with containers expanded to their subcomponents.
        self._selected_names = self._expand_containers(directly_selected)
        self._selected_lookup = _build_config_lookup([self._configs_by_name[name] for name in self._selected_names])
        #: Memoised resolved components, roots, and public-include walks, keyed by name.
        self._components: dict[str, Component] = {}
        self._roots: dict[str, Path] = {}
        self._public_includes: dict[str, list[Path]] = {}
        #: Names being resolved, outermost first, to report an integration cycle.
        self._resolving: list[str] = []

    @property
    def selected_components(self) -> list[Component]:
        """The resolved components built for this variant/platform, in selection order."""
        return [self._component(name) for name in self._selected_names]

    def _component(self, name: str) -> Component:
        config = self._lookup_config(name)
        if config.name in self._components:
            return self._components[config.name]
        if config.name in self._resolving:
            chain = " -> ".join([*self._resolving[self._resolving.index(config.name) :], config.name])
            raise UserNotificationException(f"Circular dependency detected: {chain}")
        self._resolving.append(config.name)
        self._components[config.name] = self._resolve(config)
        self._resolving.pop()
        return self._components[config.name]

    def _resolve(self, config: ComponentConfig) -> Component:
        root = self._root_for(config)
        sources = [root / source for source in config.sources]
        include_directories = self._resolve_include_directories(config, root, sources)
        # An integration component compiles the integrated sources again, with everything they need to compile.
        for integrated in self._integrated_components(config):
            sources.extend(integrated.sources)
            include_directories.extend(integrated.include_directories)
        component = Component(
            name=config.name,
            path=root,
            sources=list(OrderedDict.fromkeys(sources)),
            test_sources=[root / source for source in _declared_test_sources(config)],
            docs_sources=[root / source for source in _declared_docs_sources(config)],
            include_directories=list(OrderedDict.fromkeys(include_directories)),
            testing=config.testing,
            docs=config.docs,
            required_components=config.required_components,
            alias=config.alias,
            description=config.description,
        )
        for subcomponent_name in self._subcomponent_names(config):
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
        for dep_name in [*config.required_components, *self._subcomponent_names(config)]:
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

    def _expand_containers(self, directly_selected: list[str]) -> list[str]:
        """
        The selection with every container followed by its subcomponents, depth first.

        Maps each name to how it was selected, so a component selected twice (directly and
        through a container, or through two containers) fails naming both ways.
        """
        selection: dict[str, str] = {}
        for name in directly_selected:
            self._select(name, "directly", [], selection, set(directly_selected))
        return list(selection)

    def _select(self, name: str, origin: str, containers: list[str], selection: dict[str, str], directly_selected: set[str]) -> None:
        if name in selection:
            raise UserNotificationException(f"Component '{name}' is selected {selection[name]} and {origin}.")
        selection[name] = origin
        config = self._configs_by_name[name]
        chain = [*containers, name]
        for entry, subcomponent_name in zip(config.subcomponents, self._subcomponent_names(config), strict=True):
            if subcomponent_name in chain:
                raise UserNotificationException(f"Circular container detected: {' -> '.join([*chain[chain.index(subcomponent_name) :], subcomponent_name])}")
            # An alias resolved to the platform's own choice is already selected, not a duplicate.
            if entry != subcomponent_name and subcomponent_name in directly_selected:
                continue
            self._select(subcomponent_name, f"through container '{name}'", chain, selection, directly_selected)

    def _subcomponent_names(self, config: ComponentConfig) -> list[str]:
        """Resolved subcomponent names; every container walk passes here, so it also validates the container."""
        if config.subcomponents and (config.sources or config.include_directories or config.testing or config.test_sources):
            raise UserNotificationException(f"Container '{config.name}' must not declare sources, include directories or testing; they belong to its subcomponents.")
        return [self._entry_name(config, entry) for entry in config.subcomponents]

    def _integrated_components(self, config: ComponentConfig) -> list[Component]:
        """The components an integration component integrates, a container standing for all its subcomponents. They are resolved, never selected."""
        return [nested for entry in config.integrates for nested in _with_subcomponents(self._component(self._entry_name(config, entry)))]

    def _entry_name(self, owner: ComponentConfig, entry: str) -> str:
        """
        Resolve a ``subcomponents`` or ``integrates`` entry, a name or an alias, like ``required_components``.

        The selected component wins (the platform's alias choice), then a declared name, then
        the one declared component carrying the alias. An alias several declared components
        share, none of them selected, is ambiguous.
        """
        selected = self._selected_lookup.get(entry)
        if selected:
            return selected.name
        if entry in self._configs_by_name:
            return entry
        candidates = [config.name for config in self._configs_by_name.values() if config.alias == entry]
        if len(candidates) > 1:
            raise UserNotificationException(f"Component '{owner.name}' uses alias '{entry}'; select one of {', '.join(candidates)}.")
        if not candidates:
            raise UserNotificationException(f"Component '{entry}' not found in the declared components.")
        return candidates[0]

    def _lookup_config(self, name: str) -> ComponentConfig:
        config = self._selected_lookup.get(name) or self._configs_by_name.get(name)
        if config is None:
            raise UserNotificationException(f"Component '{name}' not found in the declared components.")
        return config
