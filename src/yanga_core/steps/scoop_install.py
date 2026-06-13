from pathlib import Path
from typing import Any

from pypeline.steps.scoop_install import ScoopInstall as PypelineScoopInstallStep
from pypeline.steps.scoop_install import ScoopManifest, ScoopManifestFile

from yanga_core.domain.config_utils import collect_configs_by_id, parse_config
from yanga_core.domain.execution_context import ExecutionContext


class ScoopInstall(PypelineScoopInstallStep[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.artifacts_locator = execution_context.spl_paths

    def _collect_manifests(self) -> list[ScoopManifestFile]:
        # Append scoped scoop fragments (variant/platform/variant-platform yanga.yaml) after the
        # base sources; a later, more specific scope overrides an earlier one (merge is last-wins).
        # Each carrier keeps its declaring file so the base get_inputs tracks edits to it.
        manifests = super()._collect_manifests()
        for cfg in collect_configs_by_id(self.execution_context, "scoop"):
            manifest = parse_config(cfg, ScoopManifest, self.project_root_dir)
            manifests.append(ScoopManifestFile(payload=manifest, file=cfg.location.file if cfg.location else None))
        return manifests

    @property
    def output_dir(self) -> Path:
        return self.artifacts_locator.variant_build_dir

    def get_name(self) -> str:
        return self.__class__.__name__
