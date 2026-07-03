"""Gather the reports of the built variants into one place so the SPL report can link to them."""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mashumaro import DataClassDictMixin
from py_app_dev.core.config import BaseConfigJSONMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.reports import REPORT_CONFIG_FILE_NAME, ReportData
from yanga_core.domain.spl_paths import SPLPaths
from yanga_core.steps.register_spl_paths import get_registered_spl_paths


@dataclass
class CollectVariantReportsConfig(DataClassDictMixin):
    #: Where the built variant reports come from: "local" (this machine) or "github-release" (not yet implemented).
    source: str = "local"


@dataclass
class CollectedVariantReport(BaseConfigJSONMixin):
    """One built variant report gathered into the SPL site; the hand-off to GenerateSplReportConfig."""

    variant: str
    platform: str
    #: Path to the variant report's index.html, relative to the SPL report output root.
    index_html: Path
    build_type: str | None = None


class CollectVariantReports(PipelineStep[ExecutionContext]):
    """
    Discover every built variant report on disk and gather it into the SPL site.

    Discovery is marker-based: a variant build writes its ``report_config.json`` next to the
    rendered ``reports/`` directory (GenerateReportConfig), so this step just globs the variant
    build root for variant-scope markers instead of re-deriving producer paths from the project
    configuration. Whatever was built is collected — including stale builds of since-removed
    variants; the local SPL site is an overview of the build tree, not of the configuration.

    The collected layout mirrors the build tree under ``<spl_report_dir>/variants/`` and, with
    the CollectedVariantReport registrations, forms the provenance-free contract: every source
    deposits into the same destination, so downstream steps never care whether a report was
    built locally or downloaded. ``github-release`` (later) downloads straight into the same
    structure.
    """

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.user_config = CollectVariantReportsConfig.from_dict(config) if config else CollectVariantReportsConfig()

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_needs_dependency_management(self) -> bool:
        # Always re-collect so the registry is populated for the downstream config step.
        return False

    def run(self) -> int:
        spl_paths = get_registered_spl_paths(self.execution_context)
        output_root = spl_paths.spl_report_dir
        if self.user_config.source != "local":
            raise UserNotificationException(f"CollectVariantReports source '{self.user_config.source}' is not implemented yet (only 'local').")

        #: Deposit area inside the SPL site where the collected variant reports land.
        collected_variants_dir = output_root / "variants"
        collected = 0
        for marker in sorted(spl_paths.variants_build_root.rglob(REPORT_CONFIG_FILE_NAME)):
            report_dir = marker.parent / SPLPaths.REPORTS_DIR_NAME
            if not (report_dir / "index.html").is_file():
                continue  # this build rendered no report
            try:
                report_data = ReportData.from_json_file(marker)
            except Exception:
                self.logger.warning(f"Skipping {marker}: not a readable report config.")
                continue
            # Component builds write their own markers into the same tree; only variant-scope
            # markers denote a collectible report.
            if not (report_data.has_variant_scope and report_data.variant_name and report_data.platform_name):
                continue

            dest = collected_variants_dir / marker.parent.relative_to(spl_paths.variants_build_root)
            # Delete-before-copy keeps the deposit an exact mirror of the step's own previous
            # output; the source report is never touched. Ceiling: full re-copy per run — with
            # hundreds of reports, switch to an incremental filecmp-based mirror sync and prune
            # deposits whose marker vanished.
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(report_dir, dest)

            index_html = dest.joinpath("index.html").relative_to(output_root)
            self.execution_context.data_registry.insert(
                CollectedVariantReport(
                    variant=report_data.variant_name,
                    platform=report_data.platform_name,
                    index_html=index_html,
                    build_type=report_data.build_type,
                ),
                self.get_name(),
            )
            self.logger.info(f"Collected variant report {marker.parent.relative_to(spl_paths.variants_build_root)} -> {index_html}")
            collected += 1

        if not collected:
            self.logger.warning("No built variant reports found; build a variant first (e.g. 'yanga run --variant <v> --platform <p>').")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        # Not statically known: the output root comes from the registered SPLPaths at run time.
        return []

    def update_execution_context(self) -> None:
        pass
