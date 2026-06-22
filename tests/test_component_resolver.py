from pathlib import Path

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.domain.component_resolver import ComponentResolver, resolve_include_directories
from yanga_core.domain.components import Component
from yanga_core.domain.config import ComponentConfig, IncludeDirectory, IncludeDirectoryScope, TestingConfig
from yanga_core.domain.spl_paths import SPLPaths


def make_resolver(
    configs: list[ComponentConfig],
    selected: list[str] | None = None,
    root: Path = Path("prj/root"),
    external_projects: dict[str, Path] | None = None,
) -> ComponentResolver:
    selected_names = selected if selected is not None else [config.name for config in configs]
    return ComponentResolver(configs, selected_names, SPLPaths(root, "variant", "platform", "debug"), external_projects)


def resolved(resolver: ComponentResolver, name: str) -> Component:
    return next(component for component in resolver.selected_components if component.name == name)


@pytest.fixture
def configs() -> list[ComponentConfig]:
    return [
        ComponentConfig(
            name="compA",
            required_components=["compB"],
            include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC), IncludeDirectory("src", IncludeDirectoryScope.PRIVATE)],
            path=Path("a"),
        ),
        ComponentConfig(name="compB", required_components=["compC"], include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("b")),
        ComponentConfig(
            name="compC",
            include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC), IncludeDirectory("src", IncludeDirectoryScope.PRIVATE)],
            path=Path("c"),
        ),
        ComponentConfig(name="compD", required_components=["compB", "compC"], include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("d")),
        ComponentConfig(name="circA", required_components=["circB"]),
        ComponentConfig(name="circB", required_components=["circA"]),
    ]


def test_resolves_include_dirs_transitively(configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(configs, selected=["compA", "compB", "compC"])

    assert resolved(resolver, "compA").include_directories == [Path("prj/root/a/src"), Path("prj/root/a/inc"), Path("prj/root/b/inc"), Path("prj/root/c/inc")]


def test_diamond_dependency_dedups_includes(configs: list[ComponentConfig]) -> None:
    configs[0].required_components = ["compB", "compD"]  # compA -> compB and compA -> compD -> compB is a diamond
    resolver = make_resolver(configs, selected=["compA", "compB", "compC", "compD"])

    assert resolved(resolver, "compA").include_directories == [
        Path("prj/root/a/src"),
        Path("prj/root/a/inc"),
        Path("prj/root/b/inc"),
        Path("prj/root/c/inc"),
        Path("prj/root/d/inc"),
    ]


def test_component_without_dependencies(configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(configs, selected=["compC"])

    assert resolved(resolver, "compC").include_directories == [Path("prj/root/c/src"), Path("prj/root/c/inc")]


def test_required_component_resolved_by_alias() -> None:
    configs = [
        ComponentConfig(name="core", required_components=["pins"], include_directories=[IncludeDirectory("core", IncludeDirectoryScope.PUBLIC)], path=Path("core")),
        ComponentConfig(name="uno_pins", alias="pins", include_directories=[IncludeDirectory("uno", IncludeDirectoryScope.PUBLIC)], path=Path("uno")),
    ]
    resolver = make_resolver(configs, selected=["core", "uno_pins"])

    assert Path("prj/root/uno/uno") in resolved(resolver, "core").include_directories


def test_required_component_resolved_from_population_when_not_selected(configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(configs, selected=["compA"])  # compB/compC declared but not selected

    assert resolved(resolver, "compA").include_directories == [Path("prj/root/a/src"), Path("prj/root/a/inc"), Path("prj/root/b/inc"), Path("prj/root/c/inc")]


def test_duplicate_alias_in_population_does_not_collide() -> None:
    configs = [
        ComponentConfig(name="core", required_components=["pins"], include_directories=[IncludeDirectory("core", IncludeDirectoryScope.PUBLIC)], path=Path("core")),
        ComponentConfig(name="uno_pins", alias="pins", include_directories=[IncludeDirectory("uno", IncludeDirectoryScope.PUBLIC)], path=Path("uno")),
        ComponentConfig(name="nano_pins", alias="pins", include_directories=[IncludeDirectory("nano", IncludeDirectoryScope.PUBLIC)], path=Path("nano")),
    ]
    resolver = make_resolver(configs, selected=["core", "uno_pins"])  # both share alias "pins"; platform picks uno_pins

    assert Path("prj/root/uno/uno") in resolved(resolver, "core").include_directories


def test_missing_required_component_fails_fast() -> None:
    resolver = make_resolver([ComponentConfig(name="compA", required_components=["compB"], path=Path("a"))], selected=["compA"])

    with pytest.raises(UserNotificationException, match="not found in the declared components"):
        _ = resolver.selected_components


def test_circular_dependency_fails_fast(configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(configs, selected=["circA", "circB"])

    with pytest.raises(UserNotificationException, match="Circular dependency"):
        _ = resolver.selected_components


def test_selected_component_built_once_and_shared(configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(configs, selected=["compC"])

    assert resolver.selected_components[0] is resolver.selected_components[0]


def test_external_component_root_resolves_from_registry() -> None:
    config = ComponentConfig(
        name="arduino_core",
        external="ArduinoCoreAvr",
        path=Path("cores/arduino"),
        include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)],
    )
    ext_root = Path("/ws/.yanga/ext/ArduinoCoreAvr/v1.0")
    resolver = make_resolver([config], selected=["arduino_core"], external_projects={"ArduinoCoreAvr": ext_root})

    component = resolved(resolver, "arduino_core")
    assert component.path == ext_root / "cores/arduino"  # declared path joined onto the installed project
    assert component.include_directories == [ext_root / "cores/arduino/inc"]


def test_external_component_missing_project_fails_fast() -> None:
    config = ComponentConfig(name="arduino_core", external="ArduinoCoreAvr", path=Path("cores/arduino"))
    resolver = make_resolver([config], selected=["arduino_core"], external_projects={})

    with pytest.raises(UserNotificationException, match="external project 'ArduinoCoreAvr'"):
        _ = resolver.selected_components


def test_path_less_component_roots_at_its_defining_config_file_directory() -> None:
    # A component declared without a `path:` roots at the directory of the config file that
    # defined it; its sources are relative to that directory.
    config = ComponentConfig(name="integration", sources=["spled/src/spled.c"])
    config.file = Path("/proj/components/yanga.yaml")
    resolver = make_resolver([config], selected=["integration"], root=Path("/proj"))

    component = resolved(resolver, "integration")
    assert component.path == Path("/proj/components")
    assert component.sources == [Path("/proj/components/spled/src/spled.c")]


def test_resolves_source_files_and_their_parent_include_dir() -> None:
    config = ComponentConfig(name="compA", sources=["src/a.c"], path=Path("compA"))
    resolver = make_resolver([config], selected=["compA"])

    component = resolved(resolver, "compA")
    assert component.sources == [Path("prj/root/compA/src/a.c")]
    assert Path("prj/root/compA/src") in component.include_directories


def test_resolve_include_directories_aggregates_components_deduped() -> None:
    configs = [
        ComponentConfig(name="compA", required_components=["shared"], include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("a")),
        ComponentConfig(name="compB", required_components=["shared"], include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("b")),
        ComponentConfig(name="shared", include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("shared")),
    ]
    resolver = make_resolver(configs)

    # The shared include dir contributed by both compA and compB appears once.
    assert resolve_include_directories(resolver.selected_components) == [Path("prj/root/a/inc"), Path("prj/root/shared/inc"), Path("prj/root/b/inc")]


def test_is_testable_reflects_declared_test_sources() -> None:
    configs = [
        ComponentConfig(name="tested", path=Path("tested"), testing=TestingConfig(sources=["test/test_tested.cc"])),
        ComponentConfig(name="untested", path=Path("untested")),
    ]
    resolver = make_resolver(configs)

    tested = resolved(resolver, "tested")
    assert tested.is_testable is True
    assert tested.test_sources == [Path("prj/root/tested/test/test_tested.cc")]
    assert resolved(resolver, "untested").is_testable is False
