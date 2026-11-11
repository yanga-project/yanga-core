import sys
from pathlib import Path

from yanga_core.commands.run import RunCommandConfig


def test_project_dir_is_resolved(tmp_path: Path) -> None:
    project_dir = str(tmp_path / "sub" / "..")
    if sys.platform == "win32":
        # Ninja compares paths case-sensitively, but CMake writes the drive letter in upper case.
        project_dir = project_dir[0].lower() + project_dir[1:]

    assert str(RunCommandConfig(project_dir=Path(project_dir)).project_dir) == str(tmp_path.resolve())
