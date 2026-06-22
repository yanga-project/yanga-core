from dataclasses import dataclass, field
from pathlib import Path

from yanga_core.domain.config import DocsConfig, TestingConfig


@dataclass
class Component:
    """
    A resolved component — a plain domain record produced by ``ComponentResolver``.

    It carries the fully-resolved picture: the absolute ``path``, the located source files,
    and the transitive include-directory set used to compile it. It also keeps the ``testing``
    and ``docs`` configuration, because generators read settings off them (e.g. mocking
    config, documentation exclusion) — those are generation inputs, not just source lists.
    Consumers read everything off the component directly; it never calls back into the
    resolver, and it does not know the wire (``ComponentConfig``) layer.
    """

    #: Component name
    name: str
    #: Resolved absolute path (in-tree under the project, or under its external project).
    path: Path
    #: Located productive source files.
    sources: list[Path] = field(default_factory=list)
    #: Located test source files.
    test_sources: list[Path] = field(default_factory=list)
    #: Located documentation source files.
    docs_sources: list[Path] = field(default_factory=list)
    #: Resolved transitive include directories to compile this component against.
    include_directories: list[Path] = field(default_factory=list)
    #: Testing configuration — generators read its mocking settings (sources are located above).
    testing: TestingConfig | None = None
    #: Documentation configuration — generators read e.g. ``exclude_productive_code``.
    docs: DocsConfig | None = None
    #: Names of the components this component requires header files from (informational).
    required_components: list[str] = field(default_factory=list)
    #: Another name this component is referred to by.
    alias: str | None = None
    #: Component description.
    description: str | None = None
    #: Whether this component is a sub-component of another component.
    is_subcomponent: bool = False
    #: Resolved subcomponents.
    subcomponents: list["Component"] = field(default_factory=list)

    @property
    def is_testable(self) -> bool:
        return bool(self.test_sources)
