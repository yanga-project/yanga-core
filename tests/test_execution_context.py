from pathlib import Path

from yanga_core.domain.config import ComponentConfig
from yanga_core.domain.execution_context import ExecutionContext, UserVariantRequest


def make_context(tmp_path: Path) -> ExecutionContext:
    context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="variant",
        user_request=UserVariantRequest("variant"),
        selected_component_names=["comp_a"],
    )
    # The population lives on the registry (registry-as-pool); the resolver reads it back.
    context.data_registry.insert(ComponentConfig(name="comp_a", path=Path("comp_a")), provider="test")
    return context


def test_component_resolver_is_built_once_and_shared(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert context.component_resolver is context.component_resolver


def test_components_are_derived_from_the_population(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    assert [component.name for component in context.components] == ["comp_a"]


def test_resolved_component_is_memoised_through_shared_resolver(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    # The shared resolver builds each component once, so the resolved component (and its
    # already-resolved include directories) is the same instance on every access.
    assert context.components[0] is context.components[0]


def test_component_registered_after_construction_is_resolvable(tmp_path: Path) -> None:
    # A generator publishes a component config mid-pipeline (before the resolver's first
    # access, the freeze point). It must be indistinguishable from a declared component.
    context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="variant",
        user_request=UserVariantRequest("variant"),
        selected_component_names=["generated_comp"],
    )
    context.data_registry.insert(ComponentConfig(name="generated_comp", path=Path("generated_comp")), provider="SomeGenerator")

    assert [component.name for component in context.components] == ["generated_comp"]
