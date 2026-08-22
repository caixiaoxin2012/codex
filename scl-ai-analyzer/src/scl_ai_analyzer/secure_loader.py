from __future__ import annotations

import hmac
import logging
import re
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .integrity_checker import IntegrityChecker, IntegrityCheckError
from .parser import AnalysisResult, SCLParser
from .secure_xml import (
    DEFAULT_MAX_SIZE,
    DEFAULT_WARN_SIZE,
    SecurePLCXMLLoader,
    SecureXMLResult,
    XMLSecurityPolicy,
)

SUPPORTED_SECURE_SUFFIXES = frozenset({".scl", ".xml"})
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class SecureLoaderError(ValueError):
    """Base exception for unified SCL/XML secure loading."""


class SecureLoaderSizeError(SecureLoaderError):
    pass


class SecureLoaderHashError(SecureLoaderError):
    pass


class SecureLoaderHashMismatchError(SecureLoaderHashError):
    pass


class SecureLoaderHashReferenceMissingError(SecureLoaderHashError):
    pass


class SecureLoaderUnsupportedTypeError(SecureLoaderError):
    pass


@dataclass(frozen=True)
class SecureLoaderPolicy:
    max_size_bytes: int = DEFAULT_MAX_SIZE
    warn_size_bytes: int = DEFAULT_WARN_SIZE
    require_hash_reference: bool = False


@dataclass(frozen=True)
class SecureLoadResult:
    path: Path
    source: str
    file_type: str
    file_size: int
    sha256: str
    hash_status: str
    hash_reference: Path | None
    hash_seconds: float
    parse_seconds: float
    total_seconds: float
    warnings: tuple[str, ...] = ()
    text: str | None = None
    scl_analysis: AnalysisResult | None = None
    xml_result: SecureXMLResult | None = None

    @property
    def integrity_verified(self) -> bool:
        return self.hash_status.startswith("verified_")


class SecureLoader:
    """Unified, auditable loader for exported `.scl` and `.xml` files.

    Processing order is fixed: file/type/size validation -> SHA-256 calculation and
    optional reference verification -> content parsing. The parser is never invoked
    after a hash mismatch. Every success or failure is logged with provenance,
    digest (when available), timing and exception information, but never source text.
    """

    def __init__(
        self,
        *,
        policy: SecureLoaderPolicy | None = None,
        integrity_checker: IntegrityChecker | None = None,
        scl_parser: SCLParser | None = None,
        xml_loader: SecurePLCXMLLoader | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.policy = policy or SecureLoaderPolicy()
        self.integrity_checker = integrity_checker or IntegrityChecker()
        self.scl_parser = scl_parser or SCLParser()
        self.xml_loader = xml_loader or SecurePLCXMLLoader(
            XMLSecurityPolicy(
                max_size_bytes=self.policy.max_size_bytes,
                warn_size_bytes=self.policy.warn_size_bytes,
            )
        )
        self.logger = logger or get_secure_loader_logger()

    def load(
        self,
        filename: str | Path,
        *,
        source: str = "filesystem",
        expected_sha256: str | None = None,
    ) -> SecureLoadResult:
        path = Path(filename)
        source_label = self._safe_source(source)
        started = time.monotonic()
        digest: str | None = None
        hash_status = "not_checked"
        hash_reference: Path | None = None
        hash_started: float | None = None
        parse_started: float | None = None
        hash_seconds = 0.0
        parse_seconds = 0.0

        try:
            file_size, suffix, warnings = self._validate_file(path)

            hash_started = time.monotonic()
            digest = self.integrity_checker.sha256_file(path)
            hash_seconds = time.monotonic() - hash_started
            if expected_sha256 is not None:
                expected = expected_sha256.strip().lower()
                if not _SHA256.fullmatch(expected):
                    raise SecureLoaderHashError("expected_sha256 必须是 64 位十六进制 SHA-256")
                expectation_digest = expected
                expectation_kind = "expected"
            else:
                try:
                    expectation = self.integrity_checker.find_expectation(path)
                except IntegrityCheckError as exc:
                    raise SecureLoaderHashError(str(exc)) from exc
                if expectation is not None:
                    expectation_digest = expectation.expected_sha256
                    expectation_kind = expectation.reference_kind
                    hash_reference = expectation.reference_path
                else:
                    expectation_digest = None
                    expectation_kind = "none"

            if expectation_digest is not None:
                if not hmac.compare_digest(expectation_digest, digest):
                    raise SecureLoaderHashMismatchError(
                        f"SHA-256 校验失败：{path.name}；expected={expectation_digest} actual={digest}"
                    )
                hash_status = f"verified_{expectation_kind}"
            else:
                if self.policy.require_hash_reference:
                    raise SecureLoaderHashReferenceMissingError(
                        f"未找到 SHA-256 参考值：{path.name}；strict 模式拒绝解析"
                    )
                hash_status = "computed_only"
                warnings.append(
                    "未找到 .sha256 或 SHA256SUMS.txt 参考值；已计算 SHA-256，"
                    "但只能记录当前内容，不能证明与既有导出版本一致。"
                )

            parse_started = time.monotonic()
            text: str | None = None
            scl_analysis: AnalysisResult | None = None
            xml_result: SecureXMLResult | None = None

            if suffix == ".scl":
                try:
                    text = path.read_text(encoding="utf-8-sig", errors="replace")
                except OSError as exc:
                    raise SecureLoaderError(f"无法读取 SCL 文件：{exc}") from exc
                if "\ufffd" in text:
                    warnings.append("SCL 文本包含无法按 UTF-8 解码的字节，已使用替换字符；建议人工复核编码。")
                scl_analysis = self.scl_parser.parse_text(text, source_name=path.name)
            else:
                xml_result = self.xml_loader.load(path)
                warnings.extend(xml_result.warnings)

            parse_seconds = time.monotonic() - parse_started
            total_seconds = time.monotonic() - started
            result = SecureLoadResult(
                path=path,
                source=source_label,
                file_type=suffix.lstrip(".").upper(),
                file_size=file_size,
                sha256=digest,
                hash_status=hash_status,
                hash_reference=hash_reference,
                hash_seconds=hash_seconds,
                parse_seconds=parse_seconds,
                total_seconds=total_seconds,
                warnings=tuple(dict.fromkeys(warnings)),
                text=text,
                scl_analysis=scl_analysis,
                xml_result=xml_result,
            )
            self.logger.info(
                "secure_load_ok source=%s path=%s type=%s size=%d sha256=%s "
                "hash_status=%s hash_ref=%s hash_seconds=%.6f parse_seconds=%.6f "
                "total_seconds=%.6f warnings=%d",
                source_label,
                path,
                result.file_type,
                file_size,
                digest,
                hash_status,
                hash_reference or "-",
                hash_seconds,
                parse_seconds,
                total_seconds,
                len(result.warnings),
            )
            return result
        except Exception as exc:
            now = time.monotonic()
            if hash_started is not None and hash_seconds == 0.0:
                hash_seconds = now - hash_started
            if parse_started is not None and parse_seconds == 0.0:
                parse_seconds = now - parse_started
            elapsed = now - started
            self.logger.error(
                "secure_load_failed source=%s path=%s sha256=%s hash_status=%s "
                "hash_seconds=%.6f parse_seconds=%.6f total_seconds=%.6f "
                "error_type=%s error=%s",
                source_label,
                path,
                digest or "-",
                hash_status,
                hash_seconds,
                parse_seconds,
                elapsed,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            if isinstance(exc, SecureLoaderError):
                raise
            if isinstance(exc, IntegrityCheckError):
                raise SecureLoaderHashError(str(exc)) from exc
            raise SecureLoaderError(f"安全加载失败：{exc}") from exc

    def _validate_file(self, path: Path) -> tuple[int, str, list[str]]:
        if not path.exists():
            raise SecureLoaderError(f"文件不存在：{path}")
        if not path.is_file():
            raise SecureLoaderError(f"输入路径不是普通文件：{path}")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SECURE_SUFFIXES:
            raise SecureLoaderUnsupportedTypeError(
                f"仅允许 .scl/.xml 文件：{path.name}"
            )

        try:
            size = path.stat().st_size
        except OSError as exc:
            raise SecureLoaderError(f"无法读取文件属性：{exc}") from exc
        if size <= 0:
            raise SecureLoaderSizeError(f"文件为空：{path.name}")
        if size > self.policy.max_size_bytes:
            raise SecureLoaderSizeError(
                f"文件过大：{self._format_mb(size)} MB，"
                f"最大允许 {self._format_mb(self.policy.max_size_bytes)} MB"
            )

        warnings: list[str] = []
        if size >= self.policy.warn_size_bytes:
            warnings.append(
                f"文件较大：{self._format_mb(size)} MB；解析可能占用较多内存和时间。"
            )
        return size, suffix, warnings

    @staticmethod
    def _safe_source(value: str) -> str:
        cleaned = " ".join(str(value).replace("\x00", "").split())
        return cleaned[:200] or "unknown"

    @staticmethod
    def _format_mb(size: int) -> str:
        return f"{size / 1024 / 1024:.1f}"


def get_secure_loader_logger() -> logging.Logger:
    logger = logging.getLogger("scl_ai_analyzer.secure_loader")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    try:
        log_dir = Path.home() / ".scl_ai_analyzer" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "secure_loader.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger
