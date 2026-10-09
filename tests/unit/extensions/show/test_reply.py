"""The checks on what the model says: shape, hosts, numbers and names."""

from __future__ import annotations

import json

import pytest

from footystreams.extensions.show.reply import (
    ReplyError,
    ReplyRules,
    names_in,
    numbers_in,
    parse_reply,
)
from footystreams.extensions.show.textutil import fold, speakable, strip_thinking

HOSTS = {"med_a": "med_a", "med_b": "med_b", "med_c": "med_c", "Ann": "med_a", "Bob": "med_b"}
VOCABULARY = (
    "Seisund County",
    "Seisund",
    "Bukach Harriers",
    "Llosasio Sellé",
    "Sellé",
    "Zaldo Argyle",
)


def rules(**changes: object) -> ReplyRules:
    base: dict[str, object] = {
        "hosts": HOSTS,
        "memory_ids": frozenset({"mem_0000001"}),
        "allowed_names": frozenset({"Seisund County", "Llosasio Sellé"}),
        "vocabulary": VOCABULARY,
        "allowed_numbers": frozenset({"1871", "2", "27500"}),
        "min_lines": 3,
        "max_lines": 5,
        "ask_predictions": False,
    }
    return ReplyRules(**{**base, **changes})  # type: ignore[arg-type]


def line(speaker: str, text: str, **extra: object) -> dict[str, object]:
    return {"speaker_id": speaker, "text": text, **extra}


GOOD = [
    line("med_a", "Seisund County were founded in 1871 and still talk about it."),
    line(
        "med_b",
        "That is a long time to hold a grudge about a cup.",
        uses=["mem_0000001", "mem_9999999"],
    ),
    line("Ann", "Llosasio Sellé would not have it any other way."),
]


def reply(lines: list[dict[str, object]] | None = None, **extra: object) -> str:
    return json.dumps({"lines": GOOD if lines is None else lines, **extra})


def test_parse_reply__accepts_a_grounded_reply() -> None:
    parsed = parse_reply(reply(), rules())
    assert [item.speaker_id for item in parsed.lines] == ["med_a", "med_b", "med_a"]
    assert parsed.lines[1].uses == ("mem_0000001",)


def test_parse_reply__finds_the_json_inside_chatter_and_thinking() -> None:
    raw = "<think>hmm</think>Here you go:\n```json\n" + reply() + "\n```"
    assert len(parse_reply(raw, rules()).lines) == 3


@pytest.mark.parametrize("raw", ["no json here", "{not json}", "[1, 2]", '{"lines": "nope"}'])
def test_parse_reply__rejects_what_is_not_a_reply(raw: str) -> None:
    with pytest.raises(ReplyError):
        parse_reply(raw, rules())


def test_parse_reply__rejects_a_speaker_who_is_not_at_the_desk() -> None:
    bad = [*GOOD[:2], line("med_z", "I am not even here today, as it happens.")]
    with pytest.raises(ReplyError, match="not at the desk"):
        parse_reply(reply(bad), rules())


def test_parse_reply__rejects_a_number_that_is_not_in_the_facts() -> None:
    bad = [*GOOD[:2], line("med_c", "They have won it 12 times since then, as I recall.")]
    with pytest.raises(ReplyError, match="number 12"):
        parse_reply(reply(bad), rules())


def test_parse_reply__lets_a_number_with_a_thousands_separator_match() -> None:
    ok = [*GOOD[:2], line("med_c", "They fit 27,500 into that ground on a good day.")]
    assert len(parse_reply(reply(ok), rules()).lines) == 3


def test_parse_reply__rejects_a_name_the_segment_does_not_involve() -> None:
    bad = [*GOOD[:2], line("med_c", "Bukach Harriers would never have sold him, though.")]
    with pytest.raises(ReplyError, match="Bukach Harriers"):
        parse_reply(reply(bad), rules())


def test_parse_reply__lets_a_part_of_an_allowed_name_through() -> None:
    ok = [*GOOD[:2], line("med_c", "Seisund have always been like that, and Selle knows it.")]
    assert len(parse_reply(reply(ok), rules()).lines) == 3


def test_parse_reply__matches_names_without_regard_to_accents() -> None:
    bad = [*GOOD[:2], line("med_c", "Zaldo Argyle once had a keeper called that, I think.")]
    with pytest.raises(ReplyError, match="Zaldo Argyle"):
        parse_reply(reply(bad), rules())


def test_parse_reply__rejects_too_few_lines_or_one_voice() -> None:
    with pytest.raises(ReplyError, match="at least 3"):
        parse_reply(reply(GOOD[:2]), rules())
    solo = [
        line("med_a", f"This is the same host talking line {word}.")
        for word in ("one", "two", "three")
    ]
    with pytest.raises(ReplyError, match="one host"):
        parse_reply(reply(solo), rules())


def test_parse_reply__drops_lines_beyond_the_maximum() -> None:
    many = [
        line("med_a" if n % 2 else "med_b", f"Another perfectly fine line, {'x' * n}.")
        for n in range(9)
    ]
    assert len(parse_reply(reply(many), rules(max_lines=5)).lines) == 5


def test_parse_reply__makes_text_safe_for_the_font() -> None:
    odd = [
        line(
            "med_a",
            "**Bold** words \N{GRINNING FACE} and a #hashtag, with fancy \u201cquotes\u201d.",
        ),
        *GOOD[1:],
    ]
    text = parse_reply(reply(odd), rules()).lines[0].text
    assert text == 'Bold words and a hashtag, with fancy "quotes".'


def test_parse_reply__needs_predictions_when_asked() -> None:
    with pytest.raises(ReplyError, match="predictions"):
        parse_reply(reply(), rules(ask_predictions=True))
    some = [{"host_id": "med_a", "pick": "home"}, {"host_id": "Bob", "pick": "away"}]
    with pytest.raises(ReplyError, match="med_c"):
        parse_reply(reply(predictions=some), rules(ask_predictions=True))
    picks = [*some, {"host_id": "med_a", "pick": "draw"}, {"host_id": "med_c", "pick": "draw"}]
    parsed = parse_reply(reply(predictions=picks), rules(ask_predictions=True))
    assert [(p.host_id, p.pick) for p in parsed.picks] == [
        ("med_a", "home"),
        ("med_b", "away"),
        ("med_c", "draw"),
    ]


def test_parse_reply__rejects_a_repeated_line_or_one_already_on_air() -> None:
    twice = [*GOOD[:2], GOOD[1]]
    with pytest.raises(ReplyError, match="repeated"):
        parse_reply(reply(twice), rules())
    said = frozenset({"that is a long time to hold a grudge about a cup"})
    with pytest.raises(ReplyError, match="already been on air"):
        parse_reply(reply(), rules(recent=said))


def test_parse_reply__keeps_only_valid_new_memories_and_at_most_two() -> None:
    memories = [
        {"host_id": "med_a", "kind": "running_joke", "text": "The car park is always the answer."},
        {"host_id": "med_b", "kind": "gossip", "text": "Not a kind we keep around here."},
        {
            "host_id": "med_c",
            "kind": "opinion",
            "text": "Llosasio Sellé is overrated and will be found out.",
        },
        {"host_id": "med_a", "kind": "anecdote", "text": "A third memory that must be dropped."},
    ]
    parsed = parse_reply(reply(memories=memories), rules())
    assert [m.kind for m in parsed.memories] == ["running_joke"]


def test_parse_reply__refuses_a_new_memory_that_names_an_outsider() -> None:
    memories = [
        {
            "host_id": "med_a",
            "kind": "opinion",
            "text": "Zaldo Argyle will win everything, mark me.",
        }
    ]
    with pytest.raises(ReplyError, match="Zaldo Argyle"):
        parse_reply(reply(memories=memories), rules())


def test_numbers_in__strips_separators_and_keeps_decimals() -> None:
    assert numbers_in("1,200 fans and an xG of 1.16 in 90 minutes") == {"1200", "1.16", "90"}


def test_names_in__is_accent_blind_and_whole_word() -> None:
    assert names_in("Selle and Seisunders", VOCABULARY) == {"Sellé"}


def test_speakable__and_fold_and_strip_thinking() -> None:
    assert fold("Æsir Ørn Gathiški") == "AEsir Orn Gathiski"
    assert speakable("  a   b\n\nc  ") == "a b c"
    assert strip_thinking("<think>\nlong\n</think>\nanswer") == "answer"
