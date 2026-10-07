"""The architecture rules as data: which layer may import which, and what each layer may not use.

Keeping the rules here (and the checking logic elsewhere) means changing the architecture is a
data edit, reviewed against docs/design/04-architecture.md and .claude/rules/architecture.md.
"""

from __future__ import annotations

ROOT_PACKAGE = "footystreams"
MAX_MODULE_LINES = 400

# Layer -> project packages (dotted, relative to ROOT_PACKAGE) it may import besides itself.
# "*" means unrestricted (composition roots).
ALLOWED_IMPORTS: dict[str, frozenset[str]] = {
    "domain": frozenset(),
    "events": frozenset({"domain"}),
    "verify": frozenset({"domain", "events"}),
    "analytics": frozenset({"domain", "events"}),
    "sim": frozenset({"domain", "events"}),
    "extensions": frozenset({"domain", "events"}),
    "persistence": frozenset({"domain", "events"}),
    "seed": frozenset({"domain"}),
    "league": frozenset({"domain", "events", "sim", "verify", "persistence.ports"}),
    "runtime": frozenset(
        {"domain", "events", "sim", "league", "verify", "persistence", "extensions"}
    ),
    "cli": frozenset({"*"}),
    "tools": frozenset(),
}

# Layers that must stay pure and deterministic: no I/O, no wall clock, no global randomness.
PURE_LAYERS = frozenset({"domain", "events", "sim", "league", "verify"})

IMPURE_MODULES = frozenset(
    {
        "os", "pathlib", "shutil", "tempfile", "sqlite3", "sqlalchemy", "socket", "subprocess",
        "asyncio", "signal", "threading", "multiprocessing", "random", "time", "urllib", "http",
        "requests", "httpx", "numpy",
    }
)  # fmt: skip
# Logging is allowed in league (operational logging) but not in the strictly pure layers.
NO_LOGGING_LAYERS = frozenset({"domain", "events", "sim", "verify"})

# Calls that read the wall clock, whichever way the module was imported.
WALL_CLOCK_ATTRIBUTES = frozenset({"now", "utcnow", "today"})

# Builtins that do I/O or are nondeterministic across runs.
IMPURE_BUILTINS = frozenset({"open", "print", "input", "eval", "exec"})
SIM_NONDETERMINISTIC_BUILTINS = frozenset({"hash", "id"})

# libm-backed functions whose last-digit results may differ across platforms (docs/design/02 s1).
LIBM_FUNCTIONS = frozenset(
    {
        "exp", "exp2", "expm1", "log", "log2", "log10", "log1p", "pow", "sin", "cos", "tan",
        "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
        "hypot", "cbrt", "erf", "erfc", "gamma", "lgamma", "fsum", "dist",
    }
)  # fmt: skip
