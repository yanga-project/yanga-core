from pathlib import Path
from typing import Any

from poks.domain import PoksConfig
from pypeline.steps.poks_install import PoksInstall as BasePoksInstall
from pypeline.steps.poks_install import PoksManifestFile

from yanga_core.domain.config_utils import collect_configs_by_id, parse_config
from yanga_core.domain.execution_context import ExecutionContext


class PoksInstall(BasePoksInstall[ExecutionContext]):
    def __init__(self, execution_context: ExecutionContext, group_name: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.artifacts_locator = execution_context.spl_paths

    def _collect_manifests(self) -> list[PoksManifestFile]:
        # Base sources first (root poks.json + registry), then scoped poks fragments from
        # variant/platform/variant-platform yanga.yaml; a later, more specific scope wins.
        # Each carrier keeps its declaring file so the base get_inputs tracks edits to it.
        manifests = super()._collect_manifests()
        for cfg in collect_configs_by_id(self.execution_context, "poks"):
            manifest = parse_config(cfg, PoksConfig, self.project_root_dir)
            manifests.append(PoksManifestFile(payload=manifest, file=cfg.location.file if cfg.location else None))
        return manifests

    @property
    def output_dir(self) -> Path:
        return self.artifacts_locator.variant_build_dir

    def get_name(self) -> str:
        return self.__class__.__name__
