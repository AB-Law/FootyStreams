"""`uv run golden check|update`: verify or regenerate the pinned match digests.

The golden file (`tests/golden/digests.json`) changes only through `update`, and only when the
simulator's output really changed AND `SIM_VERSION` was bumped since the file was written
(docs/design/11 section 7). The case list lives in `tests/factories/golden_cases.py`.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from footystreams.domain.canonical import canonical_json
from footystreams.domain.versions import SIM_VERSION
from footystreams.tools.paths import PROJECT_ROOT

GOLDEN_PATH = PROJECT_ROOT / "tests" / "golden" / "digests.json"
EXIT_STALE = 1
EXIT_NEEDS_BUMP = 2

Entry = Mapping[str, str | int]


def compute_golden() -> dict[str, object]:
    """Play every pinned case and return the document that would be written."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    cases = importlib.import_module("tests.factories.golden_cases")
    return {
        "sim_version": SIM_VERSION,
        "config_hash": cases.golden_config_hash(),
        "cases": {case.name: cases.golden_entry(case) for case in cases.CASES},
    }


def load_golden(path: Path = GOLDEN_PATH) -> dict[str, object] | None:
    """Read the golden file, or None when it does not exist yet."""
    if not path.is_file():
        return None
    document: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return document


def differences(current: Mapping[str, object], stored: Mapping[str, object] | None) -> list[str]:
    """List the cases whose pinned values differ (all of them when nothing is stored)."""
    if stored is None:
        return ["golden file missing"]
    found = []
    if current["config_hash"] != stored.get("config_hash"):
        found.append("config_hash")
    new_cases, old_cases = current["cases"], stored.get("cases", {})
    assert isinstance(new_cases, dict)  # noqa: S101 - narrows the JSON shape
    assert isinstance(old_cases, dict)  # noqa: S101
    found.extend(name for name, entry in new_cases.items() if old_cases.get(name) != entry)
    return found


def update(path: Path = GOLDEN_PATH) -> int:
    """Rewrite the golden file if the output changed and SIM_VERSION was bumped."""
    current, stored = compute_golden(), load_golden(path)
    changed = differences(current, stored)
    if not changed:
        print("golden files are up to date")
        return 0
    if stored is not None and stored.get("sim_version") == SIM_VERSION:
        print(
            f"output changed for {', '.join(changed)} but SIM_VERSION is still {SIM_VERSION}; "
            "bump it in domain/versions.py (and add a fragment with sim_version_impact) first",
            file=sys.stderr,
        )
        return EXIT_NEEDS_BUMP
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(current) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path.name} for SIM_VERSION {SIM_VERSION}: {', '.join(changed)}")
    return 0


def check(path: Path = GOLDEN_PATH) -> int:
    """Return non-zero when the stored digests do not match a fresh run."""
    changed = differences(compute_golden(), load_golden(path))
    if changed:
        print(f"golden mismatch: {', '.join(changed)}", file=sys.stderr)
        return EXIT_STALE
    print("golden files match")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run `check` or `update` and return the exit code."""
    parser = argparse.ArgumentParser(prog="golden", description=__doc__)
    parser.add_argument("command", choices=("check", "update"))
    command = parser.parse_args(argv).command
    return update() if command == "update" else check()


if __name__ == "__main__":
    sys.exit(main())
