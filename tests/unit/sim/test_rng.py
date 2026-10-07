import pytest

from footystreams.sim.rng import MASK64, SimRng, splitmix64


def test_splitmix64__seed_zero__matches_published_first_output() -> None:
    _, output = splitmix64(0)
    assert output == 0xE220A8397B1DCDAF


def test_rng__same_seed__same_sequence() -> None:
    first, second = SimRng(7), SimRng(7)
    assert [first.next_u64() for _ in range(50)] == [second.next_u64() for _ in range(50)]


def test_rng__known_answer_for_seed_one() -> None:
    rng = SimRng(1)
    assert [rng.next_u64() for _ in range(3)] == _expected_seed_one()


def _expected_seed_one() -> list[int]:
    """Independent re-implementation of xoshiro256** seeded by splitmix64, kept readable."""
    state = 1
    words = []
    for _ in range(4):
        state = (state + 0x9E3779B97F4A7C15) & MASK64
        z = ((state ^ (state >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        words.append(z ^ (z >> 31))
    s = words
    out = []
    for _ in range(3):
        r = (((s[1] * 5) & MASK64) << 7 | ((s[1] * 5) & MASK64) >> 57) & MASK64
        out.append((r * 9) & MASK64)
        t = (s[1] << 17) & MASK64
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = ((s[3] << 45) | (s[3] >> 19)) & MASK64
    return out


def test_rng__different_seeds__different_sequences() -> None:
    assert SimRng(1).next_u64() != SimRng(2).next_u64()


def test_rng__negative_seed__is_accepted_and_stable() -> None:
    assert SimRng(-5).next_u64() == SimRng(-5).next_u64()


def test_u__always_in_unit_interval() -> None:
    rng = SimRng(3)
    values = [rng.u() for _ in range(2000)]
    assert all(0.0 <= value < 1.0 for value in values)


def test_u__mean_is_close_to_half() -> None:
    rng = SimRng(11)
    mean = sum(rng.u() for _ in range(20000)) / 20000
    assert abs(mean - 0.5) < 0.01


def test_u_int__stays_in_range_and_covers_it() -> None:
    rng = SimRng(5)
    values = {rng.u_int(6) for _ in range(500)}
    assert values == {0, 1, 2, 3, 4, 5}


def test_u_int__non_positive_bound__raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        SimRng(1).u_int(0)


def test_bernoulli__probability_extremes() -> None:
    rng = SimRng(1)
    assert not any(rng.bernoulli(0.0) for _ in range(100))
    assert all(rng.bernoulli(1.0) for _ in range(100))


def test_gauss__is_bounded_with_unit_variance() -> None:
    rng = SimRng(9)
    values = [rng.gauss() for _ in range(20000)]
    variance = sum(value * value for value in values) / len(values)
    assert max(abs(value) for value in values) < 3.5
    assert abs(variance - 1.0) < 0.05


def test_choice_weighted__follows_weights() -> None:
    rng = SimRng(2)
    picks = [rng.choice_weighted([1.0, 3.0]) for _ in range(4000)]
    assert 0.70 < picks.count(1) / len(picks) < 0.80


def test_choice_weighted__zero_total__raises() -> None:
    with pytest.raises(ValueError, match="positive total"):
        SimRng(1).choice_weighted([0.0, 0.0])


def test_choice_weighted__skips_zero_weights() -> None:
    rng = SimRng(4)
    assert {rng.choice_weighted([0.0, 1.0, 0.0]) for _ in range(50)} == {1}


def test_fork__same_label__same_stream_and_different_label__differs() -> None:
    root = SimRng(42)
    assert root.fork("play").next_u64() == SimRng(42).fork("play").next_u64()
    assert root.fork("play").next_u64() != root.fork("injury").next_u64()


def test_fork__drawing_from_one_stream__does_not_move_another() -> None:
    root = SimRng(42)
    play, injury = root.fork("play"), root.fork("injury")
    expected = SimRng(42).fork("injury").next_u64()
    for _ in range(100):
        play.u()
    assert injury.next_u64() == expected


def test_draws__counts_every_draw() -> None:
    rng = SimRng(1)
    rng.u()
    rng.bernoulli(0.5)
    rng.gauss()
    assert rng.draws == 6
