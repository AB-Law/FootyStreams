"""Static facts about a Python module: what it imports and what it calls."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class ImportRef:
    """One import: `module` is dotted and absolute; `name` is set for `from m import name`."""

    module: str
    name: str | None
    line: int

    @property
    def dotted(self) -> str:
        """Full dotted target, e.g. `from footystreams import sim` -> `footystreams.sim`."""
        return f"{self.module}.{self.name}" if self.name else self.module


@dataclass(frozen=True)
class CallRef:
    """One call expression: `target` is the dotted callee (`math.exp`, `open`, `datetime.now`)."""

    target: str
    line: int


def parse_source(source: str) -> ast.Module:
    """Parse module source text."""
    return ast.parse(source)


def imports_in(tree: ast.Module, module_name: str) -> list[ImportRef]:
    """List every import in a module, resolving relative imports against `module_name`."""
    found: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(ImportRef(alias.name, None, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute_base(node, module_name)
            found.extend(ImportRef(base, alias.name, node.lineno) for alias in node.names)
    return found


def _absolute_base(node: ast.ImportFrom, module_name: str) -> str:
    """Resolve the module a `from ... import` statement refers to."""
    if node.level == 0:
        return node.module or ""
    package_parts = module_name.split(".")[:-1]
    anchor = package_parts[: len(package_parts) - (node.level - 1)]
    return ".".join([*anchor, node.module] if node.module else anchor)


def calls_in(tree: ast.Module) -> list[CallRef]:
    """List every call whose callee is a plain name or an attribute chain."""
    calls = (node for node in ast.walk(tree) if isinstance(node, ast.Call))
    return [CallRef(target, node.lineno) for node in calls if (target := _dotted(node.func))]


def _dotted(node: ast.expr) -> str:
    """Return `a.b.c` for a name/attribute chain, else an empty string."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""
