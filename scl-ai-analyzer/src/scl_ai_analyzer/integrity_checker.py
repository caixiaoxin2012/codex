from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SUPPORTED_INTEGRITY_SUFFIXES = frozenset({".scl", ".xml"})
DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_MANIFEST_NAME = "SHA256SUMS.txt"
_SHA256_LINE = re.compile(r"^(?P<digest>[0-9a-fA-F]{64})\s+\*?(?P<path>.+)$")


class IntegrityCheckError(ValueError):
    """Raised when an integrity manifest or exported file is invalid."""


@dataclass(frozen=True)
class IntegrityRecord:
    path: Path
    sha256: str
    size_bytes: int
    sidecar_path: Path | None = None


@dataclass(frozen=True)
class IntegrityManifest:
    manifest_path: Path
    records: tuple[IntegrityRecord, ...]


@dataclass(frozen=True)
class IntegrityExpectation:
    expected_sha256: str
    reference_path: Path
    reference_kind: str


@dataclass(frozen=True)
class IntegrityVerification:
    path: Path
    expected_sha256: str
    actual_sha256: str | None
    status: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class IntegrityChecker:
    """Generate and verify SHA-256 hashes for exported SCL/XML files.

    Hashing is streamed in chunks so large XML files are not loaded into memory.
    Generated manifests use the conventional `sha256  relative/path` format and
    per-file `.sha256` sidecars use the file name only, making them portable when
    an export directory is copied to another engineering workstation.
    """

    def __init__(self, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        self.chunk_size = chunk_size

    def sha256_file(self, filename: str | Path) -> str:
        path = Path(filename)
        if not path.exists():
            raise IntegrityCheckError(f"文件不存在：{path}")
        if not path.is_file():
            raise IntegrityCheckError(f"不是普通文件：{path}")

        digest = hashlib.sha256()
        try:
            with path.open("rb") as stream:
                while True:
                    chunk = stream.read(self.chunk_size)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError as exc:
            raise IntegrityCheckError(f"无法读取文件 {path}：{exc}") from exc
        return digest.hexdigest()

    def find_expectation(
        self,
        filename: str | Path,
        *,
        manifest_name: str = DEFAULT_MANIFEST_NAME,
    ) -> IntegrityExpectation | None:
        """Find a trusted-by-location SHA-256 reference without hashing the target.

        Per-file sidecars take precedence over the directory manifest. Any referenced
        path must resolve to the requested file; malformed or escaping paths are
        rejected rather than silently ignored.
        """

        path = Path(filename)
        target = path.resolve()
        sidecar = Path(str(path) + ".sha256")
        if sidecar.is_file():
            try:
                lines = [
                    line.strip()
                    for line in sidecar.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                ]
            except (OSError, UnicodeError) as exc:
                raise IntegrityCheckError(f"无法读取 SHA-256 sidecar：{exc}") from exc
            if len(lines) != 1:
                raise IntegrityCheckError(f"SHA-256 sidecar 必须包含且仅包含一条有效记录：{sidecar}")
            match = _SHA256_LINE.match(lines[0])
            if not match:
                raise IntegrityCheckError(f"SHA-256 sidecar 格式无效：{sidecar}")
            referenced = (sidecar.parent / match.group("path").strip()).resolve()
            if referenced != target:
                raise IntegrityCheckError(
                    f"SHA-256 sidecar 指向的文件与目标不一致：{sidecar}"
                )
            return IntegrityExpectation(
                expected_sha256=match.group("digest").lower(),
                reference_path=sidecar,
                reference_kind="sidecar",
            )

        manifest = path.parent / manifest_name
        if not manifest.is_file():
            return None

        base = manifest.parent.resolve()
        try:
            lines = manifest.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as exc:
            raise IntegrityCheckError(f"无法读取 SHA-256 清单：{exc}") from exc

        found: IntegrityExpectation | None = None
        for line_number, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = _SHA256_LINE.match(line)
            if not match:
                raise IntegrityCheckError(f"SHA-256 清单第 {line_number} 行格式无效")
            candidate = (base / match.group("path").strip()).resolve()
            if not candidate.is_relative_to(base):
                raise IntegrityCheckError(
                    f"SHA-256 清单第 {line_number} 行路径越界：{match.group('path').strip()}"
                )
            if candidate != target:
                continue
            expectation = IntegrityExpectation(
                expected_sha256=match.group("digest").lower(),
                reference_path=manifest,
                reference_kind="manifest",
            )
            if found is not None and found.expected_sha256 != expectation.expected_sha256:
                raise IntegrityCheckError(f"SHA-256 清单中目标文件存在冲突记录：{path.name}")
            found = expectation
        return found

    def generate(
        self,
        files: Iterable[str | Path],
        *,
        manifest_path: str | Path | None = None,
        write_sidecars: bool = True,
    ) -> IntegrityManifest:
        paths = self._normalize_files(files)
        if not paths:
            raise IntegrityCheckError("没有可生成 SHA-256 的 .scl/.xml 文件")

        root = self._common_root(paths)
        target = Path(manifest_path) if manifest_path else root / DEFAULT_MANIFEST_NAME
        target.parent.mkdir(parents=True, exist_ok=True)

        records: list[IntegrityRecord] = []
        for path in paths:
            digest = self.sha256_file(path)
            sidecar_path: Path | None = None
            if write_sidecars:
                sidecar_path = Path(str(path) + ".sha256")
                sidecar_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
            records.append(
                IntegrityRecord(
                    path=path,
                    sha256=digest,
                    size_bytes=path.stat().st_size,
                    sidecar_path=sidecar_path,
                )
            )

        manifest_root = target.parent.resolve()
        lines: list[str] = []
        for record in records:
            resolved = record.path.resolve()
            try:
                relative = resolved.relative_to(manifest_root)
                display = relative.as_posix()
            except ValueError:
                display = os.path.relpath(resolved, manifest_root).replace("\\", "/")
            lines.append(f"{record.sha256}  {display}")

        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return IntegrityManifest(manifest_path=target, records=tuple(records))

    def generate_directory(
        self,
        directory: str | Path,
        *,
        recursive: bool = True,
        manifest_name: str = DEFAULT_MANIFEST_NAME,
        write_sidecars: bool = True,
    ) -> IntegrityManifest:
        root = Path(directory)
        if not root.is_dir():
            raise IntegrityCheckError(f"导出目录不存在：{root}")
        iterator = root.rglob("*") if recursive else root.glob("*")
        files = [
            path
            for path in iterator
            if path.is_file() and path.suffix.lower() in SUPPORTED_INTEGRITY_SUFFIXES
        ]
        return self.generate(
            files,
            manifest_path=root / manifest_name,
            write_sidecars=write_sidecars,
        )

    def verify_manifest(self, manifest_path: str | Path) -> tuple[IntegrityVerification, ...]:
        manifest = Path(manifest_path)
        if not manifest.is_file():
            raise IntegrityCheckError(f"SHA-256 清单不存在：{manifest}")

        base = manifest.parent.resolve()
        results: list[IntegrityVerification] = []
        try:
            lines = manifest.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as exc:
            raise IntegrityCheckError(f"无法读取 SHA-256 清单：{exc}") from exc

        for line_number, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = _SHA256_LINE.match(line)
            if not match:
                raise IntegrityCheckError(f"SHA-256 清单第 {line_number} 行格式无效")

            expected = match.group("digest").lower()
            relative_text = match.group("path").strip()
            candidate = (base / relative_text).resolve()
            if not candidate.is_relative_to(base):
                results.append(
                    IntegrityVerification(
                        path=candidate,
                        expected_sha256=expected,
                        actual_sha256=None,
                        status="unsafe_path",
                    )
                )
                continue
            if not candidate.is_file():
                results.append(
                    IntegrityVerification(
                        path=candidate,
                        expected_sha256=expected,
                        actual_sha256=None,
                        status="missing",
                    )
                )
                continue

            actual = self.sha256_file(candidate)
            status = "ok" if hmac.compare_digest(expected, actual) else "mismatch"
            results.append(
                IntegrityVerification(
                    path=candidate,
                    expected_sha256=expected,
                    actual_sha256=actual,
                    status=status,
                )
            )

        return tuple(results)

    def verify_sidecar(self, filename: str | Path) -> IntegrityVerification:
        path = Path(filename)
        sidecar = Path(str(path) + ".sha256")
        if not sidecar.is_file():
            raise IntegrityCheckError(f"SHA-256 sidecar 不存在：{sidecar}")
        expectation = self.find_expectation(path)
        if expectation is None or expectation.reference_kind != "sidecar":
            raise IntegrityCheckError(f"无法从 sidecar 取得 SHA-256：{sidecar}")
        expected = expectation.expected_sha256
        if not path.is_file():
            return IntegrityVerification(path, expected, None, "missing")
        actual = self.sha256_file(path)
        status = "ok" if hmac.compare_digest(expected, actual) else "mismatch"
        return IntegrityVerification(path, expected, actual, status)

    @staticmethod
    def _normalize_files(files: Iterable[str | Path]) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[Path] = set()
        for value in files:
            path = Path(value)
            if path.suffix.lower() not in SUPPORTED_INTEGRITY_SUFFIXES:
                continue
            if not path.is_file():
                raise IntegrityCheckError(f"导出文件不存在或不是文件：{path}")
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(path)
        return tuple(sorted(result, key=lambda item: str(item).casefold()))

    @staticmethod
    def _common_root(paths: tuple[Path, ...]) -> Path:
        parents = [str(path.resolve().parent) for path in paths]
        return Path(os.path.commonpath(parents))


def generate_export_integrity(
    files: Iterable[str | Path],
    *,
    manifest_path: str | Path | None = None,
) -> IntegrityManifest:
    """Convenience helper used by export pipelines."""

    return IntegrityChecker().generate(
        files,
        manifest_path=manifest_path,
        write_sidecars=True,
    )
