from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_MAX_SIZE = 500 * 1024 * 1024
DEFAULT_WARN_SIZE = 200 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_NODES = 2_000_000
DEFAULT_MAX_DEPTH = 128
DEFAULT_MAX_ATTRIBUTES = 128

# The set is deliberately broad enough for common TIA Portal XML exports. Unknown
# nodes are warnings by default because Siemens export schemas vary by release and
# object type. Set strict_allowed_nodes=True to make this an enforced allow-list.
DEFAULT_ALLOWED_LOCAL_NAMES = frozenset(
    {
        "Document",
        "Engineering",
        "Project",
        "ObjectList",
        "Objects",
        "AttributeList",
        "Attribute",
        "Name",
        "Number",
        "ProgrammingLanguage",
        "SW.Blocks.FB",
        "SW.Blocks.FC",
        "SW.Blocks.OB",
        "SW.Blocks.DB",
        "SW.Types.PlcStruct",
        "SW.Types.PlcEnum",
        "Interface",
        "Sections",
        "Section",
        "Member",
        "Members",
        "CompileUnit",
        "NetworkSource",
        "FlgNet",
        "Parts",
        "Part",
        "Wires",
        "Wire",
        "Source",
        "StructuredText",
        "Text",
        "Token",
        "MultilingualText",
        "MultilingualTextItem",
        "Comment",
        "BooleanAttribute",
        "IntegerAttribute",
        "StringAttribute",
    }
)


class PLCXMLLoadError(ET.ParseError):
    """Base exception for rejected or invalid PLC XML input.

    It derives from ElementTree.ParseError so existing TIA adapter error handling can
    treat rejected XML like a per-file parse failure instead of aborting the project.
    """


class XMLSizeLimitError(PLCXMLLoadError):
    pass


class XMLParseTimeoutError(PLCXMLLoadError):
    pass


class XMLNodePolicyError(PLCXMLLoadError):
    pass


@dataclass(frozen=True)
class XMLSecurityPolicy:
    max_size_bytes: int = DEFAULT_MAX_SIZE
    warn_size_bytes: int = DEFAULT_WARN_SIZE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_nodes: int = DEFAULT_MAX_NODES
    max_depth: int = DEFAULT_MAX_DEPTH
    max_attributes_per_node: int = DEFAULT_MAX_ATTRIBUTES
    allowed_local_names: frozenset[str] = field(
        default_factory=lambda: DEFAULT_ALLOWED_LOCAL_NAMES
    )
    strict_allowed_nodes: bool = False
    reject_dtd_and_entities: bool = True


@dataclass(frozen=True)
class SecureXMLResult:
    root: ET.Element
    file_size: int
    node_count: int
    max_depth: int
    elapsed_seconds: float
    warnings: tuple[str, ...] = ()


class SecurePLCXMLLoader:
    """Validate and parse PLC/TIA XML with bounded resource policies.

    The timeout is cooperative: it is checked between parser events. The size,
    node-count, depth and DTD/entity checks are hard limits. This keeps the loader
    portable on Windows without spawning a second process for every XML file.
    """

    def __init__(
        self,
        policy: XMLSecurityPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.policy = policy or XMLSecurityPolicy()
        self.logger = logger or get_xml_security_logger()

    def load(self, filename: str | Path) -> SecureXMLResult:
        path = Path(filename)
        started = time.monotonic()

        try:
            self._validate_file(path)
            size = path.stat().st_size
            warnings: list[str] = []
            if size >= self.policy.warn_size_bytes:
                warnings.append(
                    f"XML 文件较大：{self._format_mb(size)} MB；解析可能占用较多内存。"
                )

            if self.policy.reject_dtd_and_entities:
                self._reject_forbidden_declarations(path)

            result = self._iterparse(path, size, warnings, started)
            self.logger.info(
                "xml_parse_ok path=%s size=%d nodes=%d depth=%d elapsed=%.3f warnings=%d",
                path,
                result.file_size,
                result.node_count,
                result.max_depth,
                result.elapsed_seconds,
                len(result.warnings),
            )
            return result
        except PLCXMLLoadError as exc:
            self.logger.warning("xml_parse_rejected path=%s reason=%s", path, exc)
            raise
        except ET.ParseError as exc:
            self.logger.warning("xml_parse_invalid path=%s reason=%s", path, exc)
            raise PLCXMLLoadError(f"XML 格式错误：{exc}") from exc
        except OSError as exc:
            self.logger.exception("xml_parse_io_error path=%s", path)
            raise PLCXMLLoadError(f"无法读取 XML 文件：{exc}") from exc

    def _validate_file(self, path: Path) -> None:
        if not path.exists():
            raise PLCXMLLoadError(f"工程文件不存在：{path}")
        if not path.is_file():
            raise PLCXMLLoadError(f"输入路径不是文件：{path}")
        if path.suffix.lower() != ".xml":
            raise PLCXMLLoadError(f"仅允许 XML 文件：{path.name}")

        size = path.stat().st_size
        if size <= 0:
            raise PLCXMLLoadError("XML 工程文件为空")
        if size > self.policy.max_size_bytes:
            raise XMLSizeLimitError(
                f"XML 工程文件过大：{self._format_mb(size)} MB，"
                f"最大允许 {self._format_mb(self.policy.max_size_bytes)} MB"
            )

    def _reject_forbidden_declarations(self, path: Path) -> None:
        # Scan bytes in chunks instead of loading a potentially 500 MB file at once.
        needles = (b"<!doctype", b"<!entity")
        overlap = b""
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                lowered = (overlap + chunk).lower()
                if any(needle in lowered for needle in needles):
                    raise XMLNodePolicyError(
                        "检测到 DTD/ENTITY 声明；为防止实体扩展类 XML 攻击，已拒绝解析。"
                    )
                overlap = lowered[-32:]

    def _iterparse(
        self,
        path: Path,
        size: int,
        warnings: list[str],
        started: float,
    ) -> SecureXMLResult:
        node_count = 0
        depth = 0
        max_depth_seen = 0
        unknown_names: list[str] = []
        unknown_seen: set[str] = set()

        iterator = ET.iterparse(path, events=("start", "end"))
        for event, element in iterator:
            self._check_timeout(started)

            if event == "start":
                node_count += 1
                depth += 1
                max_depth_seen = max(max_depth_seen, depth)

                if node_count > self.policy.max_nodes:
                    raise XMLNodePolicyError(
                        f"XML 节点数量超过限制：>{self.policy.max_nodes:,}"
                    )
                if depth > self.policy.max_depth:
                    raise XMLNodePolicyError(
                        f"XML 嵌套深度超过限制：>{self.policy.max_depth}"
                    )
                if len(element.attrib) > self.policy.max_attributes_per_node:
                    raise XMLNodePolicyError(
                        f"节点 {self._local_name(element.tag)} 属性数量超过限制："
                        f">{self.policy.max_attributes_per_node}"
                    )

                local_name = self._local_name(element.tag)
                if (
                    self.policy.allowed_local_names
                    and local_name not in self.policy.allowed_local_names
                ):
                    if self.policy.strict_allowed_nodes:
                        raise XMLNodePolicyError(f"XML 节点不在允许列表中：{local_name}")
                    if local_name not in unknown_seen and len(unknown_names) < 20:
                        unknown_seen.add(local_name)
                        unknown_names.append(local_name)
            else:
                depth = max(0, depth - 1)

        root = iterator.root
        if root is None:
            raise PLCXMLLoadError("XML 未生成根节点")

        if unknown_names:
            suffix = "" if len(unknown_names) < 20 else "（仅显示前 20 类）"
            warnings.append(
                "发现未在当前 TIA 节点允许列表中的节点："
                + ", ".join(unknown_names)
                + suffix
                + "。当前为兼容模式，仅告警；strict 模式会拒绝。"
            )

        elapsed = time.monotonic() - started
        return SecureXMLResult(
            root=root,
            file_size=size,
            node_count=node_count,
            max_depth=max_depth_seen,
            elapsed_seconds=elapsed,
            warnings=tuple(warnings),
        )

    def _check_timeout(self, started: float) -> None:
        timeout = self.policy.timeout_seconds
        if timeout <= 0 or time.monotonic() - started > timeout:
            raise XMLParseTimeoutError(
                f"XML 解析超过时间限制：{timeout:.1f} 秒，已中止。"
            )

    @staticmethod
    def _local_name(tag: str) -> str:
        return str(tag).rsplit("}", 1)[-1]

    @staticmethod
    def _format_mb(size: int) -> str:
        return f"{size / 1024 / 1024:.1f}"


def get_xml_security_logger() -> logging.Logger:
    logger = logging.getLogger("scl_ai_analyzer.xml_security")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    try:
        log_dir = Path.home() / ".scl_ai_analyzer" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "xml_security.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger
