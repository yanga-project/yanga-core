"""
Command line utility to fix buggy HTML links in Sphinx-generated documentation.

Searches for links with pattern href="./some/path/file.html#http://" and replaces them
with proper relative paths like href="../../some/path/file.html". The marker denotes
generated HTML outside this Sphinx site (its own nav, no way back), so the fixed links
also open in a new tab.
"""

import re
from argparse import ArgumentParser, Namespace
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from py_app_dev.core.cmd_line import Command, register_arguments_for_config_dataclass
from py_app_dev.core.config import BaseConfigJSONMixin
from py_app_dev.core.logging import logger, time_it

from .base import create_config


class FileProcessResult(NamedTuple):
    """Result of processing a single HTML file."""

    file_path: Path
    fixes_count: int
    success: bool
    error_message: str = ""


def _create_replacement(match: re.Match[str], relative_depth: int) -> str:
    """Create the replacement string for a matched buggy link."""
    original_path = match.group(1)  # Extract "./some/path/file.html"
    path_prefix = "../" * relative_depth
    fixed_path = path_prefix + original_path[2:]  # Remove "./" and add appropriate "../"
    return f'href="{fixed_path}" target="_blank" rel="noopener"'


def _fix_single_file(html_file: Path, report_root: Path, pattern: str) -> FileProcessResult:
    """Process a single HTML file - designed for parallel execution."""
    try:
        content = html_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return FileProcessResult(html_file, 0, False, f"Could not read {html_file} as UTF-8")
    except Exception as e:
        return FileProcessResult(html_file, 0, False, f"Error reading {html_file}: {e}")

    # Calculate the relative path prefix for this file
    relative_depth = len(html_file.relative_to(report_root).parts) - 1

    # Use regex substitution with a lambda that calls our replacement function
    link_pattern = re.compile(pattern)
    modified_content, fixes_count = link_pattern.subn(lambda match: _create_replacement(match, relative_depth), content)

    if fixes_count == 0:
        return FileProcessResult(html_file, 0, True)

    # Write the modified content back to the file
    try:
        html_file.write_text(modified_content, encoding="utf-8")
    except Exception as e:
        return FileProcessResult(html_file, fixes_count, False, f"Error writing to {html_file}: {e}")

    return FileProcessResult(html_file, fixes_count, True)


#: Marker links to generated HTML living outside the Sphinx site (see module docstring).
LINK_PATTERN = re.compile(r'href="(\./[^"]*\.html)#http://"')


def fix_html_links(report_dir: Path) -> list[FileProcessResult]:
    """Fix all marker links under a report root; shared by the CLI command and the SPL report step."""
    html_files = list(report_dir.rglob("*.html"))
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(_fix_single_file, html_file, report_dir, LINK_PATTERN.pattern) for html_file in html_files]
        return [future.result() for future in as_completed(futures)]


@dataclass
class CommandArgs(BaseConfigJSONMixin):
    report_dir: Path = field(metadata={"help": "Root directory of the HTML report to fix"})
    verbose: bool = field(default=False, metadata={"help": "Enable detailed logging", "action": "store_true"})


class FixHtmlLinksCommand(Command):
    def __init__(self) -> None:
        super().__init__("fix_html_links", "Fix buggy HTML links in Sphinx-generated documentation.")
        self.logger = logger.bind()
        self._verbose = False

    def log_info(self, message: str) -> None:
        """Log info message only if verbose mode is enabled."""
        if self._verbose:
            self.logger.info(message)

    def log_debug(self, message: str) -> None:
        """Log debug message only if verbose mode is enabled."""
        if self._verbose:
            self.logger.debug(message)

    def log_warning(self, message: str) -> None:
        """Log warning message only if verbose mode is enabled."""
        if self._verbose:
            self.logger.warning(message)

    @time_it("fix_html_links")
    def run(self, args: Namespace) -> int:
        cli_args = create_config(CommandArgs, args)
        self._verbose = cli_args.verbose

        if not cli_args.report_dir.exists():
            self.logger.error(f"Report root directory does not exist: {cli_args.report_dir}")
            return 1

        if not cli_args.report_dir.is_dir():
            self.logger.error(f"Report root path is not a directory: {cli_args.report_dir}")
            return 1

        self.log_info(f"Fixing HTML links in: {cli_args.report_dir}")

        results = fix_html_links(cli_args.report_dir)
        total_files = len(results)

        if total_files == 0:
            self.logger.info("No HTML files found to process")
            return 0

        total_fixes = 0
        fixed_files = 0
        errors = []

        for result in results:
            if not result.success:
                errors.append(result.error_message)
                if self._verbose:
                    self.logger.error(result.error_message)
            elif result.fixes_count > 0:
                fixed_files += 1
                total_fixes += result.fixes_count
                self.log_info(f"Fixed {result.fixes_count} links in {result.file_path}")

        self.logger.info(f"Processed {total_files} HTML files")
        self.logger.info(f"Fixed {total_fixes} links in {fixed_files} files")

        if errors:
            self.logger.warning(f"Encountered {len(errors)} errors during processing")
            if not self._verbose:
                self.logger.info("Use --verbose flag to see detailed error messages")

        return 1 if errors else 0

    def _find_html_files(self, root_dir: Path) -> Iterator[Path]:
        """Efficiently find all HTML files in the directory tree."""
        return root_dir.rglob("*.html")

    def _register_arguments(self, parser: ArgumentParser) -> None:
        register_arguments_for_config_dataclass(parser, CommandArgs)
