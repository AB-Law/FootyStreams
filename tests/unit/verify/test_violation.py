import pytest
from hypothesis import given
from hypothesis import strategies as st

from footystreams.verify import Violation, format_violations
from tests.helpers.assertions import assert_no_violations


def test_str__with_subject__appends_it() -> None:
    assert str(Violation("M04", "score mismatch", "mch_1:00042")) == (
        "[M04] score mismatch (mch_1:00042)"
    )


def test_str__without_subject__omits_it() -> None:
    assert str(Violation("W03", "ledger does not balance")) == "[W03] ledger does not balance"


@given(st.lists(st.builds(Violation, st.text(max_size=4), st.text(max_size=8)), max_size=6))
def test_format_violations__is_independent_of_input_order(violations: list[Violation]) -> None:
    assert format_violations(violations) == format_violations(list(reversed(violations)))


def test_assert_no_violations__empty__passes() -> None:
    assert_no_violations([])


def test_assert_no_violations__some__fails_listing_all_of_them() -> None:
    violations = [Violation("M02", "time went backwards"), Violation("M01", "gap in seq")]

    with pytest.raises(AssertionError) as raised:
        assert_no_violations(violations)

    message = str(raised.value)
    assert message.index("[M01]") < message.index("[M02]")
