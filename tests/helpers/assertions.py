from collections.abc import Iterable

from footystreams.verify import Violation, format_violations


def assert_no_violations(violations: Iterable[Violation]) -> None:
    """Fail with a readable list of every violation if there is at least one."""
    found = list(violations)
    assert not found, "\n" + format_violations(found)
