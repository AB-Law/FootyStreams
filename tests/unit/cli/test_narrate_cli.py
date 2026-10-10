"""narrate CLI writes a commentary script from packed match facts."""

from __future__ import annotations

from pathlib import Path

from footystreams.cli.narrate import main


def test_narrate__template_engine_writes_commentary_json(tmp_path: Path) -> None:
    out = tmp_path / "commentary.json"
    brief_out = tmp_path / "brief.json"
    code = main(
        [
            "--home",
            "SEI",
            "--away",
            "BUK",
            "--seed",
            "2",
            "--engine",
            "template",
            "--out",
            str(out),
            "--brief-out",
            str(brief_out),
        ]
    )
    assert code == 0
    assert out.is_file()
    assert brief_out.is_file()
    text = out.read_text(encoding="utf-8")
    assert '"lines"' in text
    assert '"beat"' in text
