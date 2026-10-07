import pytest

from footystreams.events.clock import match_clock, match_elapsed_s, period_elapsed_s


@pytest.mark.parametrize(
    ("period", "elapsed", "minute", "stoppage", "second"),
    [
        (1, 0, 0, 0, 0),
        (1, 125, 2, 0, 5),
        (1, 2699, 44, 0, 59),
        (1, 2700 + 130, 45, 2, 10),
        (2, 0, 45, 0, 0),
        (2, 2700, 90, 0, 0),
        (2, 2700 + 61, 90, 1, 1),
    ],
)
def test_match_clock__regulation_and_stoppage(
    period: int, elapsed: int, minute: int, stoppage: int, second: int
) -> None:
    clock = match_clock(period, elapsed)
    assert (clock.minute, clock.stoppage, clock.second) == (minute, stoppage, second)


@pytest.mark.parametrize("period", [1, 2, 3, 4])
@pytest.mark.parametrize("elapsed", [0, 59, 60, 899, 900, 2699, 2700, 2900])
def test_period_elapsed_s__inverts_match_clock(period: int, elapsed: int) -> None:
    assert period_elapsed_s(match_clock(period, elapsed)) == elapsed


def test_match_elapsed_s__continues_across_periods() -> None:
    assert match_elapsed_s(match_clock(2, 10)) == 2710
