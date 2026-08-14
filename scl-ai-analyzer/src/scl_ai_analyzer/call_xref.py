from __future__ import annotations

from dataclasses import dataclass

from .project import ProjectResult, SourceBlock
from .source_reverse import ReverseSourceIndex


@dataclass(frozen=True)
class BlockCallReference:
    caller_block: str
    caller_type: str
    target_name: str
    resolved_block: str | None
    resolved_type: str | None
    instance_name: str | None
    call_kind: str
    source_file: str
    line_number: int
    source_line: str
    state: str | None = None
    related_objects: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlockCallCrossReference:
    block_name: str
    block_type: str
    incoming: tuple[BlockCallReference, ...]
    outgoing: tuple[BlockCallReference, ...]
    root_paths: tuple[tuple[str, ...], ...]


class BlockCallCrossReferenceAnalyzer:
    """Resolve project-wide FB/FC/OB/DB call references and OB-rooted paths.

    FB instance calls are resolved through the instance's declared FB type. Direct
    calls are resolved by block name. Unresolved calls remain explicit and are not
    guessed. State context comes from the existing reverse source index.
    """

    def build(self, project: ProjectResult) -> dict[str, BlockCallCrossReference]:
        block_map = {self._norm(block.name): block for block in project.blocks}
        refs: list[BlockCallReference] = []

        for block in project.blocks:
            reverse = ReverseSourceIndex().build(block)
            instance_map = {
                self._norm(item.name): item.fb_type.strip().strip('"')
                for item in block.analysis.instances
            }
            lines = block.text.splitlines()

            for call in block.analysis.calls:
                raw_target = call.target.strip().strip('"').lstrip("#")
                normalized_target = self._norm(raw_target)
                instance_name: str | None = None
                resolved_name: str | None = None
                resolved_type: str | None = None

                if call.call_kind == "FB Instance" or normalized_target in instance_map:
                    instance_name = raw_target
                    fb_type = call.fb_type or instance_map.get(normalized_target)
                    if fb_type:
                        candidate = block_map.get(self._norm(fb_type))
                        if candidate:
                            resolved_name = candidate.name
                            resolved_type = candidate.block_type
                else:
                    candidate = block_map.get(normalized_target)
                    if candidate:
                        resolved_name = candidate.name
                        resolved_type = candidate.block_type

                line_links = reverse.get(call.line_number, ())
                state = next((item.name for item in line_links if item.kind == "STATE"), None)
                related = tuple(
                    dict.fromkeys(
                        item.name
                        for item in line_links
                        if item.kind not in {"VARIABLE", "CALL", "STATE"}
                    )
                )
                source_line = (
                    lines[call.line_number - 1].strip()
                    if 1 <= call.line_number <= len(lines)
                    else ""
                )
                refs.append(
                    BlockCallReference(
                        caller_block=block.name,
                        caller_type=block.block_type,
                        target_name=raw_target,
                        resolved_block=resolved_name,
                        resolved_type=resolved_type,
                        instance_name=instance_name,
                        call_kind=call.call_kind,
                        source_file=block.source_file.name,
                        line_number=call.line_number,
                        source_line=source_line,
                        state=state,
                        related_objects=related,
                    )
                )

        adjacency: dict[str, set[str]] = {}
        for ref in refs:
            if ref.resolved_block:
                adjacency.setdefault(self._norm(ref.caller_block), set()).add(
                    self._norm(ref.resolved_block)
                )

        root_paths_by_target = self._build_root_paths(project, adjacency)
        result: dict[str, BlockCallCrossReference] = {}
        for block in project.blocks:
            key = self._norm(block.name)
            incoming = tuple(
                ref for ref in refs
                if ref.resolved_block and self._norm(ref.resolved_block) == key
            )
            outgoing = tuple(ref for ref in refs if self._norm(ref.caller_block) == key)
            result[key] = BlockCallCrossReference(
                block_name=block.name,
                block_type=block.block_type,
                incoming=incoming,
                outgoing=outgoing,
                root_paths=root_paths_by_target.get(key, ()),
            )
        return result

    def lookup(
        self,
        project: ProjectResult,
        block_name: str,
        *,
        cache: dict[str, BlockCallCrossReference] | None = None,
    ) -> BlockCallCrossReference | None:
        index = cache if cache is not None else self.build(project)
        return index.get(self._norm(block_name))

    def _build_root_paths(
        self,
        project: ProjectResult,
        adjacency: dict[str, set[str]],
    ) -> dict[str, tuple[tuple[str, ...], ...]]:
        display = {self._norm(block.name): block.name for block in project.blocks}
        roots = [
            self._norm(block.name)
            for block in project.blocks
            if block.block_type == "ORGANIZATION_BLOCK"
        ]
        found: dict[str, list[tuple[str, ...]]] = {}
        max_depth = max(2, len(project.blocks) + 1)

        def walk(node: str, path: tuple[str, ...]) -> None:
            found.setdefault(node, []).append(tuple(display.get(item, item) for item in path))
            if len(path) >= max_depth:
                return
            for target in sorted(adjacency.get(node, ())):
                if target in path:
                    continue
                walk(target, path + (target,))

        for root in roots:
            walk(root, (root,))

        return {
            key: tuple(dict.fromkeys(paths))
            for key, paths in found.items()
        }

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().strip('"').lstrip("#").casefold()
