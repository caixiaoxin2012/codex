from __future__ import annotations

from pathlib import Path

from .parser import SCLParser
from .project import ProjectAnalyzer, ProjectResult
from .secure_loader import SecureLoader


class SecureProjectAnalyzer(ProjectAnalyzer):
    """ProjectAnalyzer variant whose `.scl` reads always pass SecureLoader first."""

    def __init__(
        self,
        parser: SCLParser | None = None,
        secure_loader: SecureLoader | None = None,
    ) -> None:
        super().__init__(parser=parser)
        self.secure_loader = secure_loader or SecureLoader(scl_parser=self.parser)

    def scan(self, path: str | Path) -> ProjectResult:
        root = Path(path)
        if root.is_file():
            files = (root,)
            project_root = root.parent
        elif root.is_dir():
            files = tuple(sorted(root.rglob("*.scl")))
            project_root = root
        else:
            raise FileNotFoundError(f"Project path not found: {root}")

        blocks = []
        for file_path in files:
            loaded = self.secure_loader.load(
                file_path,
                source=f"scl_project:{project_root}",
            )
            text = loaded.text or ""
            blocks.extend(self.split_blocks(text, file_path))

        return ProjectResult(
            root=project_root,
            source_files=files,
            blocks=tuple(blocks),
        )
