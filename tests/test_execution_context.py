from pathlib import Path

import pytest

from yanga_core.domain.config import ComponentConfig, FeatureSelectionConfig, PlatformConfig, VariantConfig, VariantPlatformsConfig
from yanga_core.domain.execution_context import ExecutionContext, UserRequest, UserRequestScope, UserRequestTarget, UserVariantRequest
from yanga_core.domain.reports import ReportRelevantFiles, ReportRelevantFileType


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


def test_user_request_round_trips_through_report_files(tmp_path: Path) -> None:
    # The report config step writes the request to JSON; the SPL coordinates and the
    # step flags in ``extra`` must both survive.
    request = UserRequest(UserRequestScope.VARIANT, variant_name="Disco", platform_name="zephyr", target=UserRequestTarget.FEATURES, extra={"gui": False})
    files = ReportRelevantFiles(target=request, file_type=ReportRelevantFileType.OTHER, files_to_be_included=[Path("a.md")])

    assert ReportRelevantFiles.from_json(files.to_json_string()) == files
    assert files.target.extra["gui"] is False


@pytest.mark.parametrize(
    ("declared", "product", "platform"),
    [
        ("both", "variants/Disco/config.txt", "variants/Disco/zephyr.txt"),
        ("product", "variants/Disco/config.txt", None),
        ("none", None, None),
    ],
    ids=["both", "product-only", "none"],
)
def test_feature_selection_files_follow_the_variant_declarations(tmp_path: Path, declared: str, product: str | None, platform: str | None) -> None:
    for relative in ("variants/Disco/yanga.yaml", "variants/Disco/config.txt", "variants/Disco/zephyr.txt"):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).touch()
    context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="Disco",
        user_request=UserRequest(UserRequestScope.VARIANT, variant_name="Disco", platform_name="zephyr"),
        platform=PlatformConfig(name="zephyr"),
        variant=VariantConfig(
            name="Disco",
            feature_selection=FeatureSelectionConfig(file="config.txt") if declared != "none" else None,
            platforms={"zephyr": VariantPlatformsConfig(feature_selection=FeatureSelectionConfig(file="zephyr.txt"))} if declared == "both" else None,
            file=tmp_path / "variants/Disco/yanga.yaml",
        ),
        create_yanga_build_dir=False,
    )

    assert context.variant_feature_selection_file == (tmp_path / product if product else None)
    assert context.variant_platform_feature_selection_file == (tmp_path / platform if platform else None)
