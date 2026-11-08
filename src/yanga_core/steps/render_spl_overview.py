"""Render the SPL overview page from the collected publish manifests."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from mashumaro import DataClassDictMixin
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger
from pypeline.domain.execution_context import ExecutionContext
from pypeline.domain.pipeline import PipelineStep

from yanga_core.domain.generated_file import GeneratedFile
from yanga_core.domain.publish_manifest import ManifestEntry, PublishKind, PublishManifest
from yanga_core.domain.reports import ReportScope
from yanga_core.steps.register_spl_paths import get_registered_spl_paths


@dataclass
class RenderSplOverviewConfig(DataClassDictMixin):
    #: Product-line display name; defaults to the project directory name.
    project_name: str = ""
    #: Jinja2 template the project owns, relative to the project root.
    template: str = "spl_overview.html.jinja"


@dataclass
class OverviewBuild:
    platform: str
    build_type: str | None
    commit: str | None
    build_time: str
    reports: list[ManifestEntry]
    artifacts: list[ManifestEntry]


@dataclass
class OverviewVariant:
    name: str
    description: str | None
    features: dict[str, Any]
    builds: list[OverviewBuild]


@dataclass
class SplOverview:
    """The data the overview template gets as ``overview``."""

    project_name: str
    generated_at: str
    commit: str | None = None
    documentation: list[ManifestEntry] = field(default_factory=list)
    variants: list[OverviewVariant] = field(default_factory=list)


def create_overview(project_name: str, manifests: list[PublishManifest]) -> SplOverview:
    overview = SplOverview(project_name=project_name, generated_at=datetime.now(UTC).isoformat(timespec="seconds"))
    for spl_manifest in (manifest for manifest in manifests if manifest.scope == ReportScope.SPL):
        overview.commit = spl_manifest.commit
        overview.documentation.extend(spl_manifest.entries)
    variant_manifests = sorted(
        (manifest for manifest in manifests if manifest.scope == ReportScope.VARIANT and manifest.variant),
        key=lambda manifest: (manifest.variant or "", manifest.platform or "", manifest.build_type or ""),
    )
    for variant_name, group in groupby(variant_manifests, key=lambda manifest: manifest.variant or ""):
        builds = list(group)
        # Stale builds may describe an older variant; the newest build has the current facts.
        latest = max(builds, key=lambda manifest: manifest.build_time)
        overview.variants.append(
            OverviewVariant(
                name=variant_name,
                description=latest.description,
                features=latest.features,
                builds=[
                    OverviewBuild(
                        platform=build.platform or "",
                        build_type=build.build_type,
                        commit=build.commit,
                        build_time=build.build_time,
                        reports=[entry for entry in build.entries if entry.kind == PublishKind.REPORT],
                        artifacts=[entry for entry in build.entries if entry.kind == PublishKind.ARTIFACT],
                    )
                    for build in builds
                ],
            )
        )
    return overview


class RenderSplOverview(PipelineStep[ExecutionContext]):
    """Render the project's overview template to the site root, one card per variant with links to its reports and artifacts."""

    def __init__(self, execution_context: ExecutionContext, group_name: str | None = None, config: dict[str, Any] | None = None) -> None:
        super().__init__(execution_context, group_name, config)
        self.logger = logger.bind()
        self.user_config = RenderSplOverviewConfig.from_dict(config) if config else RenderSplOverviewConfig()

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_needs_dependency_management(self) -> bool:
        return False

    def run(self) -> int:
        template_file = self.project_root_dir / self.user_config.template
        if not template_file.is_file():
            raise UserNotificationException(f"SPL overview template not found at {template_file}.")
        overview = create_overview(
            self.user_config.project_name or self.project_root_dir.name,
            self.execution_context.data_registry.find_data(PublishManifest),
        )
        environment = Environment(loader=FileSystemLoader(template_file.parent), autoescape=True, undefined=StrictUndefined)
        output_file = get_registered_spl_paths(self.execution_context).spl_overview_file
        GeneratedFile(output_file, environment.get_template(template_file.name).render(overview=overview)).to_file()
        self.logger.info(f"Rendered SPL overview with {len(overview.variants)} variant(s) to {output_file}")
        return 0

    def get_inputs(self) -> list[Path]:
        return []

    def get_outputs(self) -> list[Path]:
        return []

    def update_execution_context(self) -> None:
        pass
