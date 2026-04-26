"""``yanga info`` — emit the parsed project model as v1 JSON for GUI / IDE clients."""

import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path

from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.logging import logger, time_it

from yanga_core.domain.project_slurper import YangaProjectSlurper
from yanga_core.ini import YangaIni

from .base import CommandConfigBase, create_config
from .info_schema import InfoDiagnostic, build_info_project
from .run import RunCommand


@dataclass
class InfoCommandConfig(CommandConfigBase):
    output: Path | None = field(
        default=None,
        metadata={"help": "Write the JSON to this file instead of stdout. Bytes are identical to the stdout form."},
    )


class InfoCommand(Command):
    def __init__(self) -> None:
        super().__init__("info", "Emit the parsed yanga project model as JSON for GUI / IDE clients.")
        self.logger = logger.bind()

    @time_it("Info")
    def run(self, args: Namespace) -> int:
        return self.do_run(create_config(InfoCommandConfig, args))

    def do_run(self, config: InfoCommandConfig) -> int:
        ini = YangaIni.from_toml_or_ini(
            config.project_dir / "yanga.ini",
            config.project_dir / "pyproject.toml",
        )
        slurper = RunCommand.create_project_slurper(config.project_dir)
        diagnostics = self._collect_reference_diagnostics(slurper)
        info = build_info_project(config.project_dir, slurper, ini, diagnostics)
        payload = info.to_json_string() + "\n"
        if config.output:
            config.output.parent.mkdir(parents=True, exist_ok=True)
            config.output.write_text(payload)
        else:
            sys.stdout.write(payload)
        return 1 if any(d.severity == "error" for d in diagnostics) else 0

    @staticmethod
    def _collect_reference_diagnostics(slurper: YangaProjectSlurper) -> list[InfoDiagnostic]:
        diagnostics: list[InfoDiagnostic] = []
        known_components = {cfg.name for cfg in slurper.components_configs_pool.values()}
        known_platforms = {p.name for p in slurper.platforms}

        def file_str(file: Path | None) -> str | None:
            if file is None:
                return None
            try:
                return file.relative_to(slurper.project_dir.resolve()).as_posix()
            except ValueError:
                return file.as_posix()

        for variant in slurper.variants:
            for name in variant.components or []:
                if name not in known_components:
                    diagnostics.append(
                        InfoDiagnostic(
                            severity="warning",
                            message=f"Component '{name}' is referenced by variant '{variant.name}' but not defined.",
                            code="yanga.unknown_component",
                            file=file_str(variant.file),
                        )
                    )
            if variant.platforms:
                for platform_name, overlay in variant.platforms.items():
                    if platform_name not in known_platforms:
                        diagnostics.append(
                            InfoDiagnostic(
                                severity="warning",
                                message=f"Variant '{variant.name}' defines a platform overlay for '{platform_name}', which is not a known platform.",
                                code="yanga.unknown_platform_overlay",
                                file=file_str(variant.file),
                            )
                        )
                    for name in overlay.components or []:
                        if name not in known_components:
                            diagnostics.append(
                                InfoDiagnostic(
                                    severity="warning",
                                    message=f"Component '{name}' is referenced by variant '{variant.name}' (platform '{platform_name}') but not defined.",
                                    code="yanga.unknown_component",
                                    file=file_str(variant.file),
                                )
                            )

        for platform in slurper.platforms:
            for name in platform.components or []:
                if name not in known_components:
                    diagnostics.append(
                        InfoDiagnostic(
                            severity="warning",
                            message=f"Component '{name}' is referenced by platform '{platform.name}' but not defined.",
                            code="yanga.unknown_component",
                            file=file_str(platform.file),
                        )
                    )

        return diagnostics

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, InfoCommandConfig)


__all__ = ["InfoCommand", "InfoCommandConfig"]
