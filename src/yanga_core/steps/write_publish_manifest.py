"""Write the manifest of what this run publishes, for the SPL overview."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from py_app_dev.core.subprocess import SubprocessExecutor
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.execution_context import ExecutionContext as YangaExecutionContext
from yanga_core.domain.generated_file import GeneratedFile
from yanga_core.domain.publish_manifest import PUBLISH_MANIFEST_FILE_NAME, ManifestEntry, PublishedFile, PublishManifest
from yanga_core.domain.reports import FeaturesReportRelevantFile, ReportScope
from yanga_core.steps.register_spl_paths import get_registered_spl_paths


def get_commit(project_root_dir: Path) -> str | None:
    """The checked out commit; None when the project is not a git checkout or git is missing."""
    try:
        result = SubprocessExecutor(["git", "rev-parse", "HEAD"], cwd=project_root_dir, print_output=False).execute(handle_errors=False)
    except UserNotificationException:
        return None
    return result.stdout.strip() if result and result.returncode == 0 else None


def to_site_link(path: Path, site_root: Path) -> str:
    """Locally the build dir is the site root; a file outside it would need a file:// link, which breaks once the site moves."""
    if not path.is_relative_to(site_root):
        raise UserNotificationException(f"Output {path} is outside the site root {site_root}; it cannot be linked from the SPL overview.")
    return path.relative_to(site_root).as_posix()


class WritePublishManifest(PipelineStep[ExecutionContext]):
    """
    Write the manifest of the files registered for publishing in this run.

    Run it last: only outputs whose file exists are listed. In a variant build it writes a variant
    manifest into the variant build dir; in the SPL pipeline (after RegisterSplPaths) an SPL manifest
    into the SPL build dir. Locally nothing is published, so every link is relative to the build dir.
    """

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_needs_dependency_management(self) -> bool:
        # The outputs that exist change with the requested target, not with any input file.
        return False

    def create_manifest(self) -> tuple[PublishManifest, Path, Path]:
        build_time = datetime.now(UTC).isoformat(timespec="seconds")
        commit = get_commit(self.project_root_dir)
        context = self.execution_context
        if isinstance(context, YangaExecutionContext) and context.variant_name:
            features_files = context.data_registry.find_data(FeaturesReportRelevantFile)
            features_file = features_files[0].json_config_file if features_files else None
            manifest = PublishManifest(
                scope=ReportScope.VARIANT,
                build_time=build_time,
                variant=context.variant_name,
                platform=context.platform.name if context.platform else None,
                build_type=context.user_request.build_type,
                commit=commit,
                description=context.variant.description if context.variant else None,
                features=json.loads(features_file.read_text(encoding="utf-8")) if features_file and features_file.is_file() else {},
            )
            return manifest, context.spl_paths.variant_build_dir, context.spl_paths.build_dir
        spl_paths = get_registered_spl_paths(context)
        return PublishManifest(scope=ReportScope.SPL, build_time=build_time, commit=commit), spl_paths.spl_build_dir, spl_paths.build_dir

    def run(self) -> int:
        manifest, output_dir, site_root = self.create_manifest()
        for output in self.execution_context.data_registry.find_data(PublishedFile):
            if output.path.is_file():
                manifest.entries.append(ManifestEntry(kind=output.kind, name=output.name, link=to_site_link(output.path, site_root)))
        manifest_file = output_dir / PUBLISH_MANIFEST_FILE_NAME
        GeneratedFile(manifest_file, manifest.to_json_string()).to_file()
        self.logger.info(f"Wrote {manifest_file} with {len(manifest.entries)} output(s)")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        return []

    def update_execution_context(self) -> None:
        pass
