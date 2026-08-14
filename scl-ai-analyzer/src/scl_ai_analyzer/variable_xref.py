from __future__ import annotations

import re
from dataclasses import dataclass

from .project import ProjectResult, SourceBlock
from .source_reverse import ReverseSourceIndex


@dataclass(frozen=True)
class VariableReference:
    variable: str
    access: str
    block_name: str
    block_type: str
    source_file: str
    line_number: int
    source_line: str
    related_kinds: tuple[str, ...] = ()
    related_objects: tuple[str, ...] = ()


@dataclass(frozen=True)
class VariableCrossReference:
    variable: str
    declarations: tuple[VariableReference, ...]
    reads: tuple[VariableReference, ...]
    writes: tuple[VariableReference, ...]
    all_references: tuple[VariableReference, ...]


class VariableCrossReferenceAnalyzer:
    """Build project-wide variable declarations/read/write references conservatively.

    Classification is syntax based: declaration lines, assignment LHS writes,
    call-output (`=>`) writes and other occurrences as reads. The analyzer keeps
    source lines and semantic reverse-links so the GUI can navigate to states,
    alarms, devices and causal-chain objects without inventing PLC semantics.
    """

    _identifier = re.compile(r'#?"?[A-Za-z_][\w\.]*"?')
    _assignment = re.compile(
        r'^\s*(?P<target>#?"?[A-Za-z_][\w\.]*"?)\s*:=',
        re.IGNORECASE,
    )
    _call_output = re.compile(
        r'\b[A-Za-z_][\w]*\s*=>\s*(?P<target>#?"?[A-Za-z_][\w\.]*)',
        re.IGNORECASE,
    )

    def build(self, project: ProjectResult) -> dict[str, VariableCrossReference]:
        buckets: dict[str, list[VariableReference]] = {}
        display_names: dict[str, str] = {}

        for block in project.blocks:
            declared = {self._norm(item.name): item for item in block.analysis.variables}
            reverse = ReverseSourceIndex().build(block)
            declaration_lines = self._declaration_lines(block, declared)

            for normalized, variable in declared.items():
                display_names.setdefault(normalized, variable.name)
                line_number = declaration_lines.get(normalized)
                if line_number is not None:
                    self._append(
                        buckets,
                        normalized,
                        self._make_ref(
                            variable.name,
                            "DECLARE",
                            block,
                            line_number,
                            reverse,
                        ),
                    )

            lines = block.text.splitlines()
            for line_number, raw_line in enumerate(lines, start=1):
                identifiers = self._identifier.findall(raw_line)
                if not identifiers:
                    continue

                write_targets = self._write_targets(raw_line)
                declaration_names = {
                    name for name, decl_line in declaration_lines.items()
                    if decl_line == line_number
                }

                for raw_identifier in identifiers:
                    normalized = self._norm(raw_identifier)
                    if normalized in declaration_names:
                        continue

                    # Prefer known project declarations, but also index dotted/global
                    # symbols encountered in executable code so DB/tag references can
                    # participate in cross-reference before full symbol resolution exists.
                    display = display_names.get(normalized, self._display(raw_identifier))
                    if normalized not in display_names and not self._looks_variable(raw_identifier):
                        continue
                    display_names.setdefault(normalized, display)

                    access = "WRITE" if normalized in write_targets else "READ"
                    self._append(
                        buckets,
                        normalized,
                        self._make_ref(display, access, block, line_number, reverse),
                    )

        result: dict[str, VariableCrossReference] = {}
        for normalized, refs in buckets.items():
            unique = self._deduplicate(refs)
            result[normalized] = VariableCrossReference(
                variable=display_names.get(normalized, normalized),
                declarations=tuple(item for item in unique if item.access == "DECLARE"),
                reads=tuple(item for item in unique if item.access == "READ"),
                writes=tuple(item for item in unique if item.access == "WRITE"),
                all_references=tuple(unique),
            )
        return result

    def lookup(self, project: ProjectResult, variable: str) -> VariableCrossReference | None:
        return self.build(project).get(self._norm(variable))

    def variables_at(self, block: SourceBlock, line_number: int) -> tuple[str, ...]:
        lines = block.text.splitlines()
        if line_number < 1 or line_number > len(lines):
            return ()
        declared = {self._norm(item.name): item.name for item in block.analysis.variables}
        values: list[str] = []
        for token in self._identifier.findall(lines[line_number - 1]):
            normalized = self._norm(token)
            if normalized in declared:
                values.append(declared[normalized])
            elif self._looks_variable(token):
                values.append(self._display(token))
        return tuple(dict.fromkeys(values))

    def _declaration_lines(
        self,
        block: SourceBlock,
        declared: dict[str, object],
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for line_number, raw_line in enumerate(block.text.splitlines(), start=1):
            for token in self._identifier.findall(raw_line):
                normalized = self._norm(token)
                if normalized not in declared or normalized in result:
                    continue
                # SCL declarations normally contain ':' after the variable name.
                match = re.search(
                    rf'(?<![\w\.])#?"?{re.escape(self._display(token))}"?\s*:',
                    raw_line,
                    flags=re.IGNORECASE,
                )
                if match:
                    result[normalized] = line_number
        return result

    def _write_targets(self, line: str) -> set[str]:
        targets: set[str] = set()
        assignment = self._assignment.search(line)
        if assignment:
            targets.add(self._norm(assignment.group("target")))
        for match in self._call_output.finditer(line):
            targets.add(self._norm(match.group("target")))
        return targets

    def _make_ref(
        self,
        variable: str,
        access: str,
        block: SourceBlock,
        line_number: int,
        reverse: dict[int, tuple],
    ) -> VariableReference:
        lines = block.text.splitlines()
        source_line = lines[line_number - 1].strip() if 1 <= line_number <= len(lines) else ""
        links = reverse.get(line_number, ())
        related = [item for item in links if item.kind != "VARIABLE"]
        return VariableReference(
            variable=variable,
            access=access,
            block_name=block.name,
            block_type=block.block_type,
            source_file=block.source_file.name,
            line_number=line_number,
            source_line=source_line,
            related_kinds=tuple(dict.fromkeys(item.kind for item in related)),
            related_objects=tuple(dict.fromkeys(item.name for item in related)),
        )

    @staticmethod
    def _append(
        buckets: dict[str, list[VariableReference]],
        key: str,
        value: VariableReference,
    ) -> None:
        buckets.setdefault(key, []).append(value)

    @staticmethod
    def _deduplicate(items: list[VariableReference]) -> list[VariableReference]:
        seen: set[tuple[str, int, str, str]] = set()
        result: list[VariableReference] = []
        for item in items:
            key = (item.block_name.casefold(), item.line_number, item.access, item.variable.casefold())
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _looks_variable(value: str) -> bool:
        clean = value.strip().strip('"')
        return value.startswith("#") or "." in clean

    @staticmethod
    def _display(value: str) -> str:
        return value.strip().strip('"').lstrip("#")

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().strip('"').lstrip("#").casefold()
