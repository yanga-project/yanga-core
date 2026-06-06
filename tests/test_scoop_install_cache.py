"""
R1: editing a scoped scoop fragment in a yanga.yaml must re-run ScoopInstall.

The fix adds the declaring yanga.yaml to the step's get_inputs, so the executor
hashes it and detects the edit. Before the fix, scoped fragments were invisible to
the cache (silent stale install).
"""

from pathlib import Path

from pypeline.bootstrap.run import Executor, RunInfoStatus

from yanga_core.domain.config import YangaUserConfig
from yanga_core.domain.config_utils import collect_configs_by_id
from yanga_core.domain.execution_context import ExecutionContext, UserVariantRequest
from yanga_core.steps.scoop_install import ScoopInstall


def _write_project(yaml_file: Path, git_version: str) -> None:
    yaml_file.write_text(
        f"""
platforms:
  - name: test_platform
    configs:
      - id: scoop
        content:
          buckets:
            - {{name: main, source: https://github.com/ScoopInstaller/Main}}
          apps:
            - {{name: git, version: "{git_version}"}}
"""
    )


def _build_step(project_dir: Path, yaml_file: Path) -> ScoopInstall:
    user_config = YangaUserConfig.from_file(yaml_file)
    context = ExecutionContext(
        project_root_dir=project_dir,
        variant_name="test_variant",
        user_request=UserVariantRequest("test_variant"),
        platform=user_config.platforms[0],
    )
    return ScoopInstall(context, "install")


def test_get_inputs_includes_scoped_fragment_file(tmp_path: Path) -> None:
    yaml_file = tmp_path / "yanga.yaml"
    _write_project(yaml_file, "2.42")
    step = _build_step(tmp_path, yaml_file)
    assert yaml_file in step.get_inputs()


def test_get_inputs_dedups_fragment_file_and_keeps_base_inputs(tmp_path: Path) -> None:
    yaml_file = tmp_path / "yanga.yaml"
    yaml_file.write_text(
        """
platforms:
  - name: p
    configs:
      - id: scoop
        content: {apps: [{name: git}]}
      - id: scoop
        content: {apps: [{name: ninja}]}
"""
    )
    step = _build_step(tmp_path, yaml_file)
    inputs = step.get_inputs()
    assert inputs.count(yaml_file) == 1  # two fragments, one file
    assert len(inputs) > 1  # base inputs preserved alongside the fragment file


def test_editing_scoped_fragment_invalidates_cache(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    yaml_file = project_dir / "yanga.yaml"
    _write_project(yaml_file, "2.42")

    executor = Executor(cache_dir=tmp_path / "cache")
    step = _build_step(project_dir, yaml_file)
    executor.store_run_info(step)
    assert executor.previous_run_info_matches(step) == RunInfoStatus.MATCH

    # Edit the scoped scoop dependency inside the yanga.yaml.
    _write_project(yaml_file, "2.43")
    step_after = _build_step(project_dir, yaml_file)
    assert executor.previous_run_info_matches(step_after) == RunInfoStatus.FILE_CHANGED


def test_root_and_platform_files_merge_with_correct_provenance(tmp_path: Path) -> None:
    """
    Two real files merge with each fragment keeping its own provenance.

    A scoop fragment in the root yanga.yaml and another in a separate platform
    yanga.yaml are merged (union, root wins conflicts); each collected config keeps
    the file it was declared in.
    """
    root = tmp_path / "yanga.yaml"
    root.write_text(
        "configs:\n"
        "  - id: scoop\n"
        "    content:\n"
        "      buckets:\n"
        "        - {name: main, source: https://github.com/ScoopInstaller/Main}\n"
        "      apps:\n"
        '        - {name: git, source: main, version: "1.0"}\n'
    )
    platform_file = tmp_path / "platforms" / "win" / "yanga.yaml"
    platform_file.parent.mkdir(parents=True)
    platform_file.write_text(
        "platforms:\n"
        "  - name: win\n"
        "    configs:\n"
        "      - id: scoop\n"
        "        content:\n"
        "          apps:\n"
        "            - {name: ninja, source: main}\n"
        '            - {name: git, source: main, version: "2.0"}\n'  # conflicts with root -> root wins
    )

    root_config = YangaUserConfig.from_file(root)
    platform_config = YangaUserConfig.from_file(platform_file)
    context = ExecutionContext(
        project_root_dir=tmp_path,
        variant_name="v",
        user_request=UserVariantRequest("v"),
        project_configs=root_config.configs,
        platform=platform_config.platforms[0],
    )
    step = ScoopInstall(context, "install")

    # Provenance: each collected fragment points at the file it was declared in.
    collected = collect_configs_by_id(context, "scoop")
    locations = [cfg.location for cfg in collected]
    assert all(loc is not None for loc in locations)
    assert {loc.file for loc in locations if loc is not None} == {root, platform_file}
    assert set(step.get_inputs()) >= {root, platform_file}

    # Merge: union of both files, root wins the `git` conflict (first-wins).
    manifest = step._collect_dependencies()
    assert {app.name: app.version for app in manifest.apps} == {"git": "1.0", "ninja": None}
    assert {bucket.name for bucket in manifest.buckets} == {"main"}
