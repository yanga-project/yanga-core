from pathlib import Path

from yanga_core.domain.component_resolver import ComponentResolver
from yanga_core.domain.config import ComponentConfig, IncludeDirectory, IncludeDirectoryScope
from yanga_core.domain.spl_paths import SPLPaths


def test_component_alias_reproduction(tmp_path: Path) -> None:
    project_dir = tmp_path
    (project_dir / "wiring.c").write_text("")  # arduino_core's source, located during resolution

    configs = [
        ComponentConfig(name="arduino_core", sources=["wiring.c"], required_components=["pins"], include_directories=[IncludeDirectory("core", IncludeDirectoryScope.PUBLIC)]),
        ComponentConfig(name="uno_pins", alias="pins", include_directories=[IncludeDirectory(path="uno_pins", scope=IncludeDirectoryScope.PUBLIC)]),
        ComponentConfig(name="nano_pins", alias="pins", include_directories=[IncludeDirectory(path="pins_pins", scope=IncludeDirectoryScope.PUBLIC)]),
    ]
    # The platform selects uno_pins for the shared "pins" alias; nano_pins stays in the
    # population. Resolving arduino_core's required "pins" must pick the selected uno_pins.
    resolver = ComponentResolver(configs, ["arduino_core", "uno_pins"], SPLPaths(project_dir, "arduino_demo", "arduino_platform", None))
    core = next(component for component in resolver.selected_components if component.name == "arduino_core")

    assert any("uno_pins" in str(path) for path in core.include_directories), "Alias resolution missing: expected uno_pins include dir via alias"
