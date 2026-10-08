"""Determinism across processes: the same seed gives the same bytes whatever PYTHONHASHSEED is."""

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.golden
COMMAND = [
    sys.executable,
    "-m",
    "footystreams.cli.sim",
    "--demo",
    "--seed",
    "13",
    "--format",
    "ndjson",
]


def _run(hash_seed: str) -> str:
    environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
    completed = subprocess.run(  # noqa: S603 - fixed argument list, our own module
        COMMAND, capture_output=True, text=True, check=False, env=environment, timeout=60
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def test_sim__output_is_byte_identical_across_processes_and_hash_seeds() -> None:
    assert _run("1") == _run("4242")
