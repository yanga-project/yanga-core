import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from py_app_dev.core.data_registry import DataRegistry

from tests.utils import assert_element_of_type
from yanga_core.docs.sphinx import SphinxReportConfig
from yanga_core.domain.execution_context import ExecutionContext, UserRequest, UserRequestScope, UserRequestTarget
from yanga_core.domain.reports import ComponentReportData, ReportRelevantFiles, ReportRelevantFileType
from yanga_core.steps.generate_report_config import GenerateReportConfig


@pytest.fixture
def env(tmp_path: Path) -> ExecutionContext:
    env = Mock(spec=ExecutionContext)
    env.project_root_dir = tmp_path
    env.variant_name = "mock_variant"
    env.spl_paths = Mock()
    env.spl_paths.variant_build_dir = tmp_path / "build"
    env.spl_paths.get_component_build_dir = lambda name: tmp_path / "build" / name
    env.data_registry = DataRegistry()
    env.platform = None
    return env


@pytest.fixture
def env_with_platform(tmp_path: Path) -> ExecutionContext:
    env = Mock(spec=ExecutionContext)
    env.project_root_dir = tmp_path
    env.variant_name = "mock_variant"
    env.spl_paths = Mock()
    env.spl_paths.variant_build_dir = tmp_path / "build"
    env.spl_paths.get_component_build_dir = lambda name: tmp_path / "build" / name
    env.data_registry = DataRegistry()
    env.platform = Mock()
    env.platform.name = "test_platform"
    return env


def test_check_paths(env: ExecutionContext) -> None:
    """Test generating report config when no ReportRelevantFiles are registered."""
    step = GenerateReportConfig(env)
    assert step.output_dir == env.spl_paths.variant_build_dir


def test_generate_report_config_empty_registry(env: ExecutionContext) -> None:
    """Test generating report config when no ReportRelevantFiles are registered."""
    step = GenerateReportConfig(env)
    step.run()

    report_config_file = env.spl_paths.variant_build_dir / "report_config.json"
    assert report_config_file.exists()

    config_data = json.loads(report_config_file.read_text())
    assert config_data["variant_name"] == "mock_variant"
    assert config_data["platform_name"] == ""
    assert config_data["components"] == []


def test_generate_report_config_with_components(env_with_platform: ExecutionContext) -> None:
    """Test generating report config with ReportRelevantFiles for multiple components."""
    component1_docs_target = UserRequest(
        UserRequestScope.COMPONENT,
        target=UserRequestTarget.DOCS,
        component_name="component1",
    )
    component1_report_target = UserRequest(
        UserRequestScope.COMPONENT,
        target=UserRequestTarget.REPORT,
        component_name="component1",
    )
    component2_test_target = UserRequest(
        UserRequestScope.COMPONENT,
        target=UserRequestTarget.TEST,
        component_name="component2",
    )

    env_with_platform.data_registry.insert(
        ReportRelevantFiles(
            target=component1_docs_target,
            file_type=ReportRelevantFileType.DOCS,
            files_to_be_included=[Path("component1/docs/file1.md"), Path("component1/docs/file2.md")],
        ),
        "test_provider",
    )
    env_with_platform.data_registry.insert(
        ReportRelevantFiles(
            target=component1_report_target,
            file_type=ReportRelevantFileType.SOURCES,
            files_to_be_included=[Path("component1/src/main.cpp"), Path("component1/src/utils.cpp")],
        ),
        "test_provider",
    )
    env_with_platform.data_registry.insert(
        ReportRelevantFiles(
            target=component2_test_target,
            file_type=ReportRelevantFileType.TEST_RESULT,
            files_to_be_included=[Path("component2/test_results.xml")],
        ),
        "test_provider",
    )
    variant_target = UserRequest(
        UserRequestScope.VARIANT,
        target=UserRequestTarget.REPORT,
    )
    env_with_platform.data_registry.insert(
        ReportRelevantFiles(
            target=variant_target,
            file_type=ReportRelevantFileType.OTHER,
            files_to_be_included=[Path("variant_file.txt")],
        ),
        "test_provider",
    )

    step = GenerateReportConfig(env_with_platform)
    step.run()

    report_config_file = env_with_platform.spl_paths.variant_build_dir / "report_config.json"
    config_data = SphinxReportConfig.from_dict(json.loads(report_config_file.read_text()))

    assert config_data.variant_name == "mock_variant"
    assert config_data.platform_name == "test_platform"
    assert len(config_data.components) == 2

    component1_config = assert_element_of_type(config_data.components, ComponentReportData, lambda c: c.name == "component1")
    assert set(component1_config.docs_files) == {Path("component1/docs/file1.md"), Path("component1/docs/file2.md")}
    assert set(component1_config.sources) == {Path("component1/src/main.cpp"), Path("component1/src/utils.cpp")}

    component2_config = assert_element_of_type(config_data.components, ComponentReportData, lambda c: c.name == "component2")
    assert set(component2_config.test_results) == {Path("component2/test_results.xml")}

    for config in [component1_config, component2_config]:
        for field in ["lint_results", "coverage_results", "other_files"]:
            assert config.__getattribute__(field) == []
