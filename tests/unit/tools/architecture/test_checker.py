"""Canary tests: each architecture rule must actually fire on a deliberately bad module.

If one of these stops failing, the architecture gate has silently become a no-op.
"""

from pathlib import Path

import pytest

from footystreams.tools.architecture.checker import Violation, check_tree


def _check(tmp_path: Path, modules: dict[str, str]) -> list[Violation]:
    package_root = tmp_path / "footystreams"
    for relative, source in modules.items():
        path = package_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return check_tree(package_root)


def _rules(violations: list[Violation]) -> set[str]:
    return {violation.rule for violation in violations}


def test_check_tree__clean_modules__reports_nothing(tmp_path: Path) -> None:
    modules = {
        "sim/engine.py": "import math\nfrom footystreams.domain import player\nx = math.sqrt(4)\n",
        "domain/player.py": "from datetime import date\nBORN = date(2000, 1, 1)\n",
        "runtime/loop.py": "import asyncio\nimport time\nfrom footystreams.sim import engine\n",
    }

    assert _check(tmp_path, modules) == []


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("domain/a.py", "from footystreams.sim import engine\n"),
        ("domain/a.py", "import footystreams.events\n"),
        ("sim/a.py", "from footystreams.league import schedule\n"),
        ("sim/a.py", "from footystreams import persistence\n"),
        ("league/a.py", "from footystreams.persistence.sql import repos\n"),
        ("events/a.py", "from footystreams.sim.engine import run\n"),
    ],
)
def test_check_tree__upward_or_sideways_import__is_a_layering_violation(
    tmp_path: Path, module: str, source: str
) -> None:
    assert _rules(_check(tmp_path, {module: source})) == {"layering"}


def test_check_tree__relative_import__is_resolved_and_checked(tmp_path: Path) -> None:
    modules = {"domain/a.py": "from ..sim import engine\n"}

    assert _rules(_check(tmp_path, modules)) == {"layering"}


def test_check_tree__league_may_import_persistence_ports_only(tmp_path: Path) -> None:
    allowed = {"league/a.py": "from footystreams.persistence import ports\n"}
    allowed_deep = {"league/b.py": "from footystreams.persistence.ports import WorldReader\n"}

    assert _check(tmp_path, allowed | allowed_deep) == []


@pytest.mark.parametrize(
    "source",
    [
        "import random\n",
        "import numpy\n",
        "import os\n",
        "import time\n",
        "import asyncio\n",
        "from pathlib import Path\n",
        "import sqlalchemy\n",
        "data = open('x')\n",
        "print('hi')\n",
    ],
)
def test_check_tree__impure_use_in_pure_layer__is_a_purity_violation(
    tmp_path: Path, source: str
) -> None:
    assert _rules(_check(tmp_path, {"sim/a.py": source})) == {"purity"}


def test_check_tree__wall_clock_call__is_flagged_even_with_datetime_allowed(
    tmp_path: Path,
) -> None:
    source = "from datetime import datetime\nstamp = datetime.now()\n"

    assert _rules(_check(tmp_path, {"league/a.py": source})) == {"wall-clock"}


def test_check_tree__logging_banned_in_sim_but_allowed_in_league(tmp_path: Path) -> None:
    assert _rules(_check(tmp_path, {"sim/a.py": "import logging\n"})) == {"purity"}
    assert _check(tmp_path / "other", {"league/a.py": "import logging\n"}) == []


@pytest.mark.parametrize(
    "source",
    [
        "import math\ny = math.exp(1.0)\n",
        "import math\ny = math.log(2.0)\n",
        "from math import sin\n",
        "y = pow(2.0, 0.5)\n",
    ],
)
def test_check_tree__libm_function_in_sim__is_flagged(tmp_path: Path, source: str) -> None:
    assert _rules(_check(tmp_path, {"sim/a.py": source})) & {"libm", "nondeterminism"}


def test_check_tree__hash_and_id_in_sim__are_nondeterministic(tmp_path: Path) -> None:
    source = "a = hash('x')\nb = id(a)\n"

    violations = _check(tmp_path, {"sim/a.py": source})

    assert _rules(violations) == {"nondeterminism"}
    assert len(violations) == 2


def test_check_tree__runtime_and_cli_may_use_anything(tmp_path: Path) -> None:
    modules = {
        "runtime/a.py": "import os\nimport signal\nimport time\nx = time.monotonic()\n",
        "cli/a.py": (
            "from footystreams.sim import engine\nfrom footystreams.persistence import sql\n"
        ),
    }

    assert _check(tmp_path, modules) == []


def test_check_tree__undeclared_package__is_reported(tmp_path: Path) -> None:
    assert _rules(_check(tmp_path, {"mystery/a.py": "x = 1\n"})) == {"unknown-layer"}


def test_check_tree__oversized_module__is_reported(tmp_path: Path) -> None:
    source = "x = 1\n" * 401

    assert _rules(_check(tmp_path, {"domain/big.py": source})) == {"module-size"}


def test_violation__str__shows_location_rule_and_message() -> None:
    violation = Violation(Path("a.py"), 7, "layering", "bad")

    assert str(violation) == "a.py:7: [layering] bad"
