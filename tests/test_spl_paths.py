from pathlib import Path

from pypeline.domain.artifacts import ProjectArtifactsLocator

from yanga_core.domain.execution_context import ExecutionContext, UserVariantRequest
from yanga_core.domain.spl_paths import SPLPaths


def test_spl_paths_is_project_artifacts_locator(tmp_path: Path) -> None:
    spl_paths = SPLPaths(tmp_path, variant_name=None, platform_name=None, build_type=None)
    assert isinstance(spl_paths, ProjectArtifactsLocator)


def test_spl_paths_build_dir_uses_yanga_prefix(tmp_path: Path) -> None:
    spl_paths = SPLPaths(tmp_path, variant_name=None, platform_name=None, build_type=None)
    assert spl_paths.build_dir == tmp_path / ".yanga" / "build"


def test_spl_paths_build_dir_without_yanga_prefix(tmp_path: Path) -> None:
    spl_paths = SPLPaths(tmp_path, variant_name=None, platform_name=None, build_type=None, create_yanga_build_dir=False)
    assert spl_paths.build_dir == tmp_path / "build"


def test_execution_context_create_artifacts_locator_returns_spl_paths(tmp_path: Path) -> None:
    ctx = ExecutionContext(project_root_dir=tmp_path, user_request=UserVariantRequest(None))
    locator = ctx.create_artifacts_locator()
    assert isinstance(locator, SPLPaths)


def test_execution_context_create_artifacts_locator_build_dir_is_yanga(tmp_path: Path) -> None:
    ctx = ExecutionContext(project_root_dir=tmp_path, user_request=UserVariantRequest(None))
    assert ctx.create_artifacts_locator().build_dir == tmp_path / ".yanga" / "build"


def test_execution_context_create_artifacts_locator_build_dir_without_yanga(tmp_path: Path) -> None:
    ctx = ExecutionContext(project_root_dir=tmp_path, user_request=UserVariantRequest(None), create_yanga_build_dir=False)
    assert ctx.create_artifacts_locator().build_dir == tmp_path / "build"
