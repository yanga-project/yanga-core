from abc import ABC, abstractmethod
from pathlib import Path


class GeneratedFileIf(ABC):
    def __init__(self, path: Path) -> None:
        self.path = path

    @abstractmethod
    def to_string(self) -> str:
        pass

    def to_file(self) -> None:
        dir = self.path.parent
        if not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            f.write(self.to_string())


class GeneratedFile(GeneratedFileIf):
    def __init__(self, path: Path, content: str) -> None:
        super().__init__(path)
        self.content = content

    def to_string(self) -> str:
        return self.content
