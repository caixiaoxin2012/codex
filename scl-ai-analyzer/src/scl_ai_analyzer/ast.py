from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .project import BLOCK_PREFIX, ProjectResult


@dataclass(frozen=True)
class SourceRef:
    file: Path
    line: int | None = None


@dataclass(frozen=True)
class ASTNode:
    node_id: str
    kind: str
    name: str
    source: SourceRef
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ASTEdge:
    source_id: str
    target_id: str
    relation: str
    source: SourceRef
    resolved: bool = True


@dataclass(frozen=True)
class Diagnostic:
    level: str
    code: str
    message: str
    source: SourceRef | None = None


@dataclass(frozen=True)
class ProjectAST:
    root: Path
    nodes: tuple[ASTNode, ...]
    edges: tuple[ASTEdge, ...]
    diagnostics: tuple[Diagnostic, ...]

    def node_map(self) -> dict[str, ASTNode]:
        return {node.node_id: node for node in self.nodes}


class ProjectASTBuilder:
    """Build a cross-file symbol table and call graph from parsed SCL blocks."""

    def build(self, project: ProjectResult) -> ProjectAST:
        nodes: list[ASTNode] = []
        edges: list[ASTEdge] = []
        diagnostics: list[Diagnostic] = []
        symbol_by_name: dict[str, str] = {}

        for block in project.blocks:
            prefix = BLOCK_PREFIX.get(block.block_type, block.block_type)
            node_id = self._block_id(block.block_type, block.name)
            key = self._normalize(block.name)
            if key in symbol_by_name:
                diagnostics.append(
                    Diagnostic(
                        level="warning",
                        code="DUPLICATE_BLOCK",
                        message=f"Duplicate block name: {block.name}",
                        source=SourceRef(block.source_file),
                    )
                )
            else:
                symbol_by_name[key] = node_id

            nodes.append(
                ASTNode(
                    node_id=node_id,
                    kind=prefix,
                    name=block.name,
                    source=SourceRef(block.source_file, 1),
                    metadata={
                        "block_type": block.block_type,
                        "variables": str(len(block.analysis.variables)),
                        "instances": str(len(block.analysis.instances)),
                        "calls": str(len(block.analysis.calls)),
                    },
                )
            )

            for instance in block.analysis.instances:
                instance_id = f"INSTANCE:{node_id}:{self._normalize(instance.name)}"
                nodes.append(
                    ASTNode(
                        node_id=instance_id,
                        kind="INSTANCE",
                        name=instance.name,
                        source=SourceRef(block.source_file),
                        metadata={"fb_type": instance.fb_type, "owner": block.name},
                    )
                )
                target_id = symbol_by_name.get(self._normalize(instance.fb_type))
                edges.append(
                    ASTEdge(
                        source_id=node_id,
                        target_id=instance_id,
                        relation="DECLARES_INSTANCE",
                        source=SourceRef(block.source_file),
                    )
                )
                if target_id:
                    edges.append(
                        ASTEdge(
                            source_id=instance_id,
                            target_id=target_id,
                            relation="INSTANCE_OF",
                            source=SourceRef(block.source_file),
                        )
                    )

        block_ids = {self._normalize(node.name): node.node_id for node in nodes if node.kind in {"OB", "FB", "FC", "DB"}}
        for block in project.blocks:
            source_id = self._block_id(block.block_type, block.name)
            instance_types = {
                self._normalize(item.name): item.fb_type
                for item in block.analysis.instances
            }
            for call in block.analysis.calls:
                raw_target = call.target.lstrip("#").strip('"')
                normalized = self._normalize(raw_target)
                target_id = block_ids.get(normalized)
                relation = "CALLS"

                if call.target.startswith("#") and normalized in instance_types:
                    instance_id = f"INSTANCE:{source_id}:{normalized}"
                    edges.append(
                        ASTEdge(
                            source_id=source_id,
                            target_id=instance_id,
                            relation="CALLS_INSTANCE",
                            source=SourceRef(block.source_file, call.line_number),
                        )
                    )
                    continue

                if target_id is None:
                    target_id = f"UNRESOLVED:{normalized}"
                    edges.append(
                        ASTEdge(
                            source_id=source_id,
                            target_id=target_id,
                            relation=relation,
                            source=SourceRef(block.source_file, call.line_number),
                            resolved=False,
                        )
                    )
                    diagnostics.append(
                        Diagnostic(
                            level="warning",
                            code="UNRESOLVED_CALL",
                            message=f"{block.name} calls missing block {raw_target}",
                            source=SourceRef(block.source_file, call.line_number),
                        )
                    )
                else:
                    edges.append(
                        ASTEdge(
                            source_id=source_id,
                            target_id=target_id,
                            relation=relation,
                            source=SourceRef(block.source_file, call.line_number),
                        )
                    )

        called = {edge.target_id for edge in edges if edge.relation in {"CALLS", "CALLS_INSTANCE"} and edge.resolved}
        for node in nodes:
            if node.kind in {"FB", "FC"} and node.node_id not in called:
                diagnostics.append(
                    Diagnostic(
                        level="info",
                        code="ORPHAN_BLOCK",
                        message=f"Block is not called: {node.name}",
                        source=node.source,
                    )
                )

        return ProjectAST(
            root=project.root,
            nodes=tuple(nodes),
            edges=tuple(edges),
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().strip('"').casefold()

    @classmethod
    def _block_id(cls, block_type: str, name: str) -> str:
        return f"{BLOCK_PREFIX.get(block_type, block_type)}:{cls._normalize(name)}"


def render_ast_markdown(ast: ProjectAST) -> str:
    node_map = ast.node_map()
    roots = [node for node in ast.nodes if node.kind == "OB"]
    outgoing: dict[str, list[ASTEdge]] = {}
    for edge in ast.edges:
        if edge.relation not in {"CALLS", "CALLS_INSTANCE"}:
            continue
        outgoing.setdefault(edge.source_id, []).append(edge)

    lines = ["## 项目树状结构", ""]
    if not roots:
        lines.append("未识别到 OB 入口块。")
    else:
        for root in roots:
            lines.extend(_render_tree(root.node_id, node_map, outgoing, set(), 0))

    lines.extend(["", "## 项目诊断", "", "| 级别 | 代码 | 说明 | 位置 |", "|---|---|---|---|"])
    if not ast.diagnostics:
        lines.append("| info | OK | 未发现项目级结构问题 | - |")
    else:
        for item in ast.diagnostics:
            location = "-"
            if item.source:
                location = item.source.file.name
                if item.source.line:
                    location += f":{item.source.line}"
            lines.append(f"| {item.level} | {item.code} | {item.message} | {location} |")
    return "\n".join(lines)


def _render_tree(
    node_id: str,
    node_map: dict[str, ASTNode],
    outgoing: dict[str, list[ASTEdge]],
    visited: set[str],
    depth: int,
) -> list[str]:
    node = node_map.get(node_id)
    label = node.name if node else node_id
    kind = node.kind if node else "?"
    prefix = "  " * depth + "- "
    lines = [f"{prefix}{kind} `{label}`"]
    if node_id in visited:
        lines[-1] += " ↩"
        return lines
    next_visited = set(visited)
    next_visited.add(node_id)
    for edge in outgoing.get(node_id, []):
        if edge.resolved:
            lines.extend(_render_tree(edge.target_id, node_map, outgoing, next_visited, depth + 1))
        else:
            lines.append("  " * (depth + 1) + f"- unresolved `{edge.target_id.removeprefix('UNRESOLVED:')}`")
    return lines
