"""Find the publish manifests on disk so the SPL overview can link to every published file."""

from pathlib import Path
from typing import Any

from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.publish_manifest import PUBLISH_MANIFEST_FILE_NAME, PublishManifest
from yanga_core.domain.reports import ReportScope
from yanga_core.steps.register_spl_paths import get_registered_spl_paths


class CollectPublishManifests(PipelineStep[ExecutionContext]):
    """
    Register every publish manifest found under the variant and SPL build dirs.

    It reads only the disk: a download step that runs before it restores manifests and outputs
    into the same layout, so downloaded and local outputs look the same. Whatever was built is
    listed, including stale builds of removed variants. Nothing is copied.
    """

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_needs_dependency_management(self) -> bool:
        # Always run so the registry is populated for the render step.
        return False

    def run(self) -> int:
        spl_paths = get_registered_spl_paths(self.execution_context)
        manifest_files = sorted(spl_paths.variants_build_root.rglob(PUBLISH_MANIFEST_FILE_NAME))
        spl_manifest_file = spl_paths.spl_build_dir / PUBLISH_MANIFEST_FILE_NAME
        if spl_manifest_file.is_file():
            manifest_files.append(spl_manifest_file)
        for manifest_file in manifest_files:
            try:
                manifest = PublishManifest.from_json_file(manifest_file)
            except Exception:
                self.logger.warning(f"Skipping {manifest_file}: not a readable publish manifest.")
                continue
            self.execution_context.data_registry.insert(manifest, self.get_name())
            self.logger.info(f"Collected {manifest_file}")
        if not any(manifest.scope == ReportScope.VARIANT for manifest in self.execution_context.data_registry.find_data(PublishManifest)):
            self.logger.warning("No variant manifests found; build a variant first (e.g. 'yanga run --variant <v> --platform <p> --target report').")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        return []

    def update_execution_context(self) -> None:
        pass
