from __future__ import annotations

import re

import pytest

from footystreams.domain.ids import IdMint, base36, derive_id


def test_base36__known_values() -> None:
    assert base36(0) == "00000"
    assert base36(35, width=1) == "z"
    assert base36(36, width=2) == "10"


def test_base36__negative__raises() -> None:
    with pytest.raises(ValueError, match="negative"):
        base36(-1)


def test_id_mint__counts_per_kind_and_rejects_unknown_kind() -> None:
    mint = IdMint()
    assert mint.next("player") == "plr_00001"
    assert mint.next("player") == "plr_00002"
    assert mint.next("club") == "clb_00001"
    assert mint.minted("player") == 2
    with pytest.raises(ValueError, match="unknown id kind"):
        mint.next("spaceship")


def test_id_mint__snapshot_and_restore_undo_a_discarded_attempt() -> None:
    mint = IdMint()
    mint.next("player")
    saved = mint.snapshot()
    mint.next("player")
    mint.next("club")
    mint.restore(saved)
    assert mint.next("player") == "plr_00002"
    assert mint.minted("club") == 0


def test_id_mint__resumes_from_saved_counts() -> None:
    assert IdMint({"ledger": 41}).next("ledger") == "led_00016"


def test_derive_id__same_parts__same_id_and_valid_shape() -> None:
    first = derive_id("modifier", "plr_00001", "2031-08-01", "media_storm")
    assert first == derive_id("modifier", "plr_00001", "2031-08-01", "media_storm")
    assert first != derive_id("modifier", "plr_00002", "2031-08-01", "media_storm")
    assert re.fullmatch(r"mod_[0-9a-z]{10}", first)


def test_derive_id__unknown_kind__raises() -> None:
    with pytest.raises(KeyError):
        derive_id("spaceship", "x")
