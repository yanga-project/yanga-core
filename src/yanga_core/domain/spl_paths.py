import sys
from pathlib import Path

from py_app_dev.core.exceptions import UserNotificationException
from pypeline.domain.artifacts import ProjectArtifactsLocator


class SPLPaths(ProjectArtifactsLocator):
    """Provides resolved paths for an SPL project build context."""

    #: Name of the reports directory inside a build scope (variant build dir, SPL build dir).
    REPORTS_DIR_NAME = "reports"

    def __init__(
        self,
        project_root_dir: Path,
        variant_name: str | None,
        platform_name: str | None,
        build_type: str | None,
        create_yanga_build_dir: bool = True,
    ) -> None:
        super().__init__(project_root_dir)
        yanga_out_dir = project_root_dir / ".yanga"
        self.build_dir = yanga_out_dir / "build" if create_yanga_build_dir else project_root_dir / "build"
        self.variants_dir = project_root_dir / "variants"
        self.platforms_dir = project_root_dir / "platforms"
        #: Root of all variant-scope build directories; sibling of the SPL scope build dir.
        self.variants_build_root = self.build_dir / "variants"
        # Variant builds are namespaced by variant, platform, build type (whichever are set).
        parts = [part for part in (variant_name, platform_name, build_type) if part]
        self.variant_build_dir: Path = self.variants_build_root.joinpath(*parts) if parts else self.build_dir
        self.variant_dir: Path | None = self.variants_dir / variant_name if variant_name else None
        self.external_dependencies_dir = yanga_out_dir / "ext" if create_yanga_build_dir else self.build_dir / "ext"
        #: SPL scope build directory; sibling of the variant builds.
        self.spl_build_dir = self.build_dir / "spl"
        #: The self-contained SPL overview site: assembled here, publishable verbatim.
        self.spl_report_dir = self.spl_build_dir / self.REPORTS_DIR_NAME
        scripts_dir = "Scripts" if sys.platform.startswith("win32") else "bin"
        self.venv_scripts_dir = self.project_root_dir.joinpath(".venv").joinpath(scripts_dir)

    @property
    def variant_reports_dir(self) -> Path:
        """Where a variant build renders its report; the SPL report collector discovers these."""
        return self.variant_build_dir / self.REPORTS_DIR_NAME

    def locate_artifact(self, artifact: str, first_search_paths: list[Path | None]) -> Path:
        search_paths: list[Path | None] = []
        for path in first_search_paths:
            if path:
                search_paths.append(path.parent if path.is_file() else path)
        search_paths.extend(
            [
                self.variant_dir,
                self.project_root_dir,
                self.platforms_dir,
            ]
        )
        for dir in search_paths:
            if dir and (artifact_path := Path(dir).joinpath(artifact)).exists():
                return artifact_path
        else:
            raise UserNotificationException(f"Artifact '{artifact}' not found in the project. Searched paths: {', '.join(str(p) for p in search_paths if p is not None)}")

    def get_component_build_dir(self, component_name: str) -> Path:
        return self.variant_build_dir / component_name
