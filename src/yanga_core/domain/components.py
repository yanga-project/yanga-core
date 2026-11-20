from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yanga_core.domain.config import DocsConfig


@dataclass
class TestingBlock:
    """The tests of one framework with located paths; the framework's generator reads ``config`` into its own dataclass."""

    framework: str
    sources: list[Path] = field(default_factory=list)
    mockup_sources: list[Path] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class Component:
    """
    A resolved component — a plain domain record produced by ``ComponentResolver``.

    It carries the fully-resolved picture: the absolute ``path``, the located source files,
    and the transitive include-directory set used to compile it. It also keeps the ``testing``
    blocks and ``docs`` configuration, because generators read settings off them (e.g. a
    framework's ``config``, documentation exclusion) — those are generation inputs, not just source lists.
    Consumers read everything off the component directly; it never calls back into the
    resolver, and it does not know the wire (``ComponentConfig``) layer.
    """

    #: Component name
    name: str
    #: Resolved absolute path (in-tree under the project, or under its external project).
    path: Path
    #: Located productive source files.
    sources: list[Path] = field(default_factory=list)
    #: Located documentation source files.
    docs_sources: list[Path] = field(default_factory=list)
    #: Resolved transitive include directories to compile this component against.
    include_directories: list[Path] = field(default_factory=list)
    #: Testing blocks, one per test framework, with located paths.
    testing: list[TestingBlock] = field(default_factory=list)
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
    #: Names of the components an integration component compiles again, a container replaced by its subcomponents; empty otherwise.
    integrates: list[str] = field(default_factory=list)

    @property
    def test_sources(self) -> list[Path]:
        """Located test sources of all testing blocks."""
        return [source for block in self.testing for source in block.sources]

    def is_testable(self, framework: str | None = None) -> bool:
        """Whether any testing block, or the one of ``framework``, has sources."""
        return any(block.sources for block in self.testing if framework is None or block.framework == framework)

    @property
    def is_container(self) -> bool:
        return bool(self.subcomponents)
