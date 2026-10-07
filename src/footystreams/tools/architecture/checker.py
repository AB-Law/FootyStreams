"""Check a source tree against the architecture rules in `rules.py`.

Limitations (deliberate, to keep the checker simple and fast): imports are matched by name, so
`import math as m` followed by `m.exp()` is not caught; dynamic imports are not followed. The
checks are a safety net for honest mistakes, not a sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from footystreams.tools.architecture import rules
from footystreams.tools.architecture.scan import (
    CallRef,
    ImportRef,
    calls_in,
    imports_in,
    parse_source,
)


@dataclass(frozen=True)
class Violation:
    """One broken architecture rule."""

    path: Path
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        """Render as `path:line: [rule] message`."""
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


def check_tree(package_root: Path) -> list[Violation]:
    """Check every module under `package_root` (the directory of the `footystreams` package)."""
    violations: list[Violation] = []
    for path in sorted(package_root.rglob("*.py")):
        violations.extend(_check_module(path, package_root))
    return violations


def _check_module(path: Path, package_root: Path) -> list[Violation]:
    relative = path.relative_to(package_root)
    source = path.read_text(encoding="utf-8")
    violations = _size_violations(path, source)
    layer = relative.parts[0] if len(relative.parts) > 1 else None
    if layer is None:
        return violations  # modules directly in the root package have no layer rules
    if layer not in rules.ALLOWED_IMPORTS:
        return [*violations, Violation(path, 1, "unknown-layer", _unknown_layer_message(layer))]
    module_name = ".".join([rules.ROOT_PACKAGE, *relative.with_suffix("").parts])
    tree = parse_source(source)
    imports, calls = imports_in(tree, module_name), calls_in(tree)
    violations.extend(_layering_violations(path, layer, imports))
    if layer in rules.PURE_LAYERS:
        violations.extend(_purity_violations(path, layer, imports, calls))
    if layer == "sim":
        violations.extend(_sim_violations(path, imports, calls))
    return violations


def _unknown_layer_message(layer: str) -> str:
    return f"package '{layer}' is not declared in tools/architecture/rules.py (ALLOWED_IMPORTS)"


def _size_violations(path: Path, source: str) -> list[Violation]:
    lines = len(source.splitlines())
    if lines <= rules.MAX_MODULE_LINES:
        return []
    return [Violation(path, 1, "module-size", f"{lines} lines exceeds {rules.MAX_MODULE_LINES}")]


def _layering_violations(path: Path, layer: str, imports: list[ImportRef]) -> list[Violation]:
    allowed = rules.ALLOWED_IMPORTS[layer]
    if "*" in allowed:
        return []
    found = []
    for ref in imports:
        target = _project_target(ref)
        if target and not _is_allowed(layer, target, allowed):
            message = f"layer '{layer}' may not import footystreams.{target}"
            found.append(Violation(path, ref.line, "layering", message))
    return found


def _project_target(ref: ImportRef) -> str:
    """Return the imported project path relative to the root package, or '' if external."""
    prefix = f"{rules.ROOT_PACKAGE}."
    return ref.dotted.removeprefix(prefix) if ref.dotted.startswith(prefix) else ""


def _is_allowed(layer: str, target: str, allowed: frozenset[str]) -> bool:
    if target.split(".", maxsplit=1)[0] == layer:
        return True
    return any(target == item or target.startswith(f"{item}.") for item in allowed)


def _purity_violations(
    path: Path, layer: str, imports: list[ImportRef], calls: list[CallRef]
) -> list[Violation]:
    found = []
    for ref in imports:
        top = ref.module.split(".")[0]
        if top in rules.IMPURE_MODULES or (top == "logging" and layer in rules.NO_LOGGING_LAYERS):
            message = f"pure layer '{layer}' may not import '{top}'"
            found.append(Violation(path, ref.line, "purity", message))
    for call in calls:
        if call.target in rules.IMPURE_BUILTINS:
            found.append(Violation(path, call.line, "purity", f"'{call.target}()' is I/O"))
        elif "." in call.target and call.target.rsplit(".", 1)[1] in rules.WALL_CLOCK_ATTRIBUTES:
            found.append(Violation(path, call.line, "wall-clock", f"'{call.target}()' reads time"))
    return found


def _sim_violations(path: Path, imports: list[ImportRef], calls: list[CallRef]) -> list[Violation]:
    found = [
        Violation(path, ref.line, "libm", f"'math.{ref.name}' is not portable")
        for ref in imports
        if ref.module == "math" and ref.name in rules.LIBM_FUNCTIONS
    ]
    for call in calls:
        head, _, tail = call.target.rpartition(".")
        if head in {"math", "cmath"} and tail in rules.LIBM_FUNCTIONS:
            found.append(Violation(path, call.line, "libm", f"'{call.target}' is not portable"))
        elif call.target in rules.LIBM_FUNCTIONS | rules.SIM_NONDETERMINISTIC_BUILTINS:
            found.append(Violation(path, call.line, "nondeterminism", f"'{call.target}()'"))
    return found
