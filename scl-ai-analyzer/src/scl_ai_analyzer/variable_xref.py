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
    scope: str
    declarations: tuple[VariableReference, ...]
    reads: tuple[VariableReference, ...]
    writes: tuple[VariableReference, ...]
    all_references: tuple[VariableReference, ...]


class VariableCrossReferenceAnalyzer:
    """Build project-wide declaration/read/write references with PLC variable scope.

    Declared block variables are scoped to their FB/FC/OB/DB. Dotted/global symbols
    are indexed project-wide. Classification is deliberately syntax based:
    declaration lines, assignment LHS/call-output writes, and other occurrences as
    reads. Every reference keeps source and reverse-engineering context.
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
        scopes: dict[str, str] = {}

        for block in project.blocks:
            declared = {self._norm(item.name): item for item in block.analysis.variables}
            reverse = ReverseSourceIndex().build(block)
            declaration_lines = self._declaration_lines(block, declared)

            for normalized, variable in declared.items():
                key = self._local_key(block.name, normalized)
                display_names.setdefault(key, variable.name)
                scopes[key] = block.name
                line_number = declaration_lines.get(normalized)
                if line_number is not None:
                    self._append(
                        buckets,
                        key,
                        self._make_ref(variable.name, "DECLARE", block, line_number, reverse),
                    )

            for line_number, raw_line in enumerate(block.text.splitlines(), start=1):
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

                    if normalized in declared:
                        key = self._local_key(block.name, normalized)
                        display = declared[normalized].name
                        scopes[key] = block.name
                    elif self._looks_global_variable(raw_identifier):
                        key = self._global_key(normalized)
                        display = self._display(raw_identifier)
                        scopes[key] = "PROJECT"
                    else:
                        continue

                    display_names.setdefault(key, display)
                    access = "WRITE" if normalized in write_targets else "READ"
                    self._append(
                        buckets,
                        key,
                        self._make_ref(display, access, block, line_number, reverse),
                    )

        result: dict[str, VariableCrossReference] = {}
        for key, refs in buckets.items():
            unique = self._deduplicate(refs)
            result[key] = VariableCrossReference(
                variable=display_names.get(key, key),
                scope=scopes.get(key, "PROJECT"),
                declarations=tuple(item for item in unique if item.access == "DECLARE"),
                reads=tuple(item for item in unique if item.access == "READ"),
                writes=tuple(item for item in unique if item.access == "WRITE"),
                all_references=tuple(unique),
            )
        return result

    def lookup(
        self,
        project: ProjectResult,
        variable: str,
        *,
        block_name: str | None = None,
        cache: dict[str, VariableCrossReference] | None = None,
    ) -> VariableCrossReference | None:
        index = cache if cache is not None else self.build(project)
        normalized = self._norm(variable)
        if block_name:
            local = index.get(self._local_key(block_name, normalized))
            if local:
                return local
        return index.get(self._global_key(normalized))

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
            elif self._looks_global_variable(token):
                values.append(self._display(token))
        return tuple(dict.fromkeys(values))

    def cache_key(self, block: SourceBlock, variable: str) -> str:
        normalized = self._norm(variable)
        declared = {self._norm(item.name) for item in block.analysis.variables}
        if normalized in declared:
            return self._local_key(block.name, normalized)
        return self._global_key(normalized)

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
                token_name = re.escape(self._display(token))
                if re.search(
                    rf'(?<![\w\.])#?"?{token_name}"?\s*:',
                    raw_line,
                    flags=re.IGNORECASE,
                ):
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
        related = [item for item in reverse.get(line_number, ()) if item.kind != "VARIABLE"]
        return VariableReference(
            variable=variable,
            access=access,
            block_name=block.name,
            block_type=block.block_type,
            source_file=block.source_file.name,
            line_number=line_number,
            source_line=source_line,
            related_kinds=tuple(item.kind for item in related),
            related_objects=tuple(item.name for item in related),
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
        seen: set[tuple[str, str, int, str, str]] = set()
        result: list[VariableReference] = []
        for item in items:
            key = (
                item.source_file.casefold(),
                item.block_name.casefold(),
                item.line_number,
                item.access,
                item.variable.casefold(),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _looks_global_variable(value: str) -> bool:
        clean = value.strip().strip('"').lstrip("#")
        return not value.startswith("#") and "." in clean

    @staticmethod
    def _display(value: str) -> str:
        return value.strip().strip('"').lstrip("#")

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().strip('"').lstrip("#").casefold()

    @staticmethod
    def _local_key(block_name: str, normalized: str) -> str:
        return f"LOCAL:{block_name.casefold()}:{normalized}"

    @staticmethod
    def _global_key(normalized: str) -> str:
        return f"GLOBAL:{normalized}"
