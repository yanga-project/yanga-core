import re
from pathlib import Path

import pytest
from py_app_dev.core.exceptions import UserNotificationException

from yanga_core.domain.component_resolver import ComponentResolver, resolve_include_directories
from yanga_core.domain.components import Component
from yanga_core.domain.config import ComponentConfig, DocsConfig, IncludeDirectory, IncludeDirectoryScope, TestingConfig
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


@pytest.fixture
def container_configs() -> list[ComponentConfig]:
    return [
        ComponentConfig(
            name="networking",
            subcomponents=["tcp", "transport"],
            docs=DocsConfig(sources=["doc/networking.md"]),
            path=Path("net"),
        ),
        ComponentConfig(name="transport", subcomponents=["udp"], path=Path("transport")),
        ComponentConfig(name="routing", subcomponents=["udp"], path=Path("routing")),
        ComponentConfig(name="tcp", sources=["tcp.c"], include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("tcp")),
        ComponentConfig(name="udp", sources=["udp.c"], include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("udp")),
        ComponentConfig(name="app", required_components=["networking"], path=Path("app")),
    ]


def selected_names(resolver: ComponentResolver) -> list[str]:
    return [component.name for component in resolver.selected_components]


def test_container_selection_expands_nested_subcomponents_in_order(container_configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(container_configs, selected=["networking"])

    assert selected_names(resolver) == ["networking", "tcp", "transport", "udp"]
    assert resolved(resolver, "tcp").is_subcomponent is True


@pytest.mark.parametrize(
    ("selected", "message"),
    [
        (["tcp", "networking"], "Component 'tcp' is selected directly and through container 'networking'."),
        (["networking", "transport"], "Component 'transport' is selected through container 'networking' and directly."),
        (["networking", "routing"], "Component 'udp' is selected through container 'transport' and through container 'routing'."),
    ],
)
def test_component_selected_twice_fails_naming_both_ways(container_configs: list[ComponentConfig], selected: list[str], message: str) -> None:
    with pytest.raises(UserNotificationException, match=re.escape(message)):
        make_resolver(container_configs, selected=selected)


@pytest.mark.parametrize(
    "container",
    [
        ComponentConfig(name="networking", subcomponents=["tcp"], sources=["net.c"]),
        ComponentConfig(name="networking", subcomponents=["tcp"], include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)]),
        ComponentConfig(name="networking", subcomponents=["tcp"], testing=TestingConfig(sources=["test_networking.cc"])),
    ],
)
def test_container_with_own_sources_includes_or_testing_fails(container: ComponentConfig) -> None:
    with pytest.raises(UserNotificationException, match="Container 'networking' must not declare sources, include directories or testing"):
        make_resolver([container, ComponentConfig(name="tcp")], selected=["networking"])


def test_container_with_undeclared_subcomponent_fails() -> None:
    with pytest.raises(UserNotificationException, match="Component 'tcp' not found in the declared components"):
        make_resolver([ComponentConfig(name="networking", subcomponents=["tcp"])], selected=["networking"])


def test_container_cycle_fails_with_chain() -> None:
    configs = [ComponentConfig(name="outer", subcomponents=["inner"]), ComponentConfig(name="inner", subcomponents=["outer"])]

    with pytest.raises(UserNotificationException, match=re.escape("Circular container detected: outer -> inner -> outer")):
        make_resolver(configs, selected=["outer"])


def test_requiring_container_gets_subcomponents_public_includes(container_configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(container_configs, selected=["app"])

    assert resolved(resolver, "app").include_directories == [Path("prj/root/tcp/inc"), Path("prj/root/udp/inc")]


def test_integration_component_compiles_integrated_sources_without_selecting_them(container_configs: list[ComponentConfig]) -> None:
    container_configs.append(ComponentConfig(name="test_net", integrates=["networking"], sources=["stub.c"], path=Path("itest")))
    resolver = make_resolver(container_configs, selected=["test_net"])

    assert selected_names(resolver) == ["test_net"]
    assert resolved(resolver, "test_net").sources == [Path("prj/root/itest/stub.c"), Path("prj/root/tcp/tcp.c"), Path("prj/root/udp/udp.c")]


def test_integration_component_gets_all_includes_of_integrated_components(container_configs: list[ComponentConfig]) -> None:
    container_configs[3].include_directories.append(IncludeDirectory("private", IncludeDirectoryScope.PRIVATE))  # tcp
    container_configs.append(ComponentConfig(name="test_tcp", integrates=["tcp"], path=Path("itest")))
    resolver = make_resolver(container_configs, selected=["test_tcp"])

    assert resolved(resolver, "test_tcp").include_directories == [Path("prj/root/tcp/private"), Path("prj/root/tcp/inc"), Path("prj/root/tcp")]


def test_integrated_alias_uses_platform_choice(pins_configs: list[ComponentConfig]) -> None:
    pins_configs[1].sources = ["uno.c"]
    pins_configs.append(ComponentConfig(name="test_io", integrates=["pins"], path=Path("itest")))
    resolver = make_resolver(pins_configs, selected=["test_io", "uno_pins"])

    assert resolved(resolver, "test_io").sources == [Path("prj/root/uno/uno.c")]


def test_integration_cycle_fails_with_chain() -> None:
    configs = [ComponentConfig(name="first", integrates=["second"]), ComponentConfig(name="second", integrates=["first"])]
    resolver = make_resolver(configs, selected=["first"])

    with pytest.raises(UserNotificationException, match=re.escape("Circular dependency detected: first -> second -> first")):
        _ = resolver.selected_components


@pytest.fixture
def pins_configs() -> list[ComponentConfig]:
    return [
        ComponentConfig(name="io", subcomponents=["pins"]),
        ComponentConfig(name="uno_pins", alias="pins", path=Path("uno")),
        ComponentConfig(name="nano_pins", alias="pins", path=Path("nano")),
    ]


def test_subcomponent_alias_uses_platform_choice(pins_configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(pins_configs, selected=["io", "uno_pins"])

    assert selected_names(resolver) == ["io", "uno_pins"]
    assert [subcomponent.name for subcomponent in resolved(resolver, "io").subcomponents] == ["uno_pins"]


def test_subcomponent_alias_carried_by_one_component_expands_to_it(pins_configs: list[ComponentConfig]) -> None:
    resolver = make_resolver(pins_configs[:2], selected=["io"])

    assert selected_names(resolver) == ["io", "uno_pins"]


def test_subcomponent_alias_shared_by_several_unselected_components_fails(pins_configs: list[ComponentConfig]) -> None:
    with pytest.raises(UserNotificationException, match=re.escape("Component 'io' uses alias 'pins'; select one of uno_pins, nano_pins.")):
        make_resolver(pins_configs, selected=["io"])


def test_container_required_components_add_their_public_includes(container_configs: list[ComponentConfig]) -> None:
    container_configs[0].required_components = ["extra"]
    container_configs.append(ComponentConfig(name="extra", include_directories=[IncludeDirectory("inc", IncludeDirectoryScope.PUBLIC)], path=Path("extra")))
    resolver = make_resolver(container_configs, selected=["networking"])

    assert resolved(resolver, "networking").include_directories == [Path("prj/root/extra/inc"), Path("prj/root/tcp/inc"), Path("prj/root/udp/inc")]
