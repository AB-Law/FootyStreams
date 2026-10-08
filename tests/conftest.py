"""Shared pytest configuration: Hypothesis profiles.

Select a profile with the HYPOTHESIS_PROFILE environment variable:
  dev      fast feedback while coding (default)
  ci       pull-request runs
  nightly  long runs on a schedule
Deadlines are disabled on purpose: wall-clock timing must never make a test flaky.
"""

import os

import pytest
from hypothesis import settings

from tests.helpers.git_env import scrub_git_environment

settings.register_profile("dev", max_examples=20, deadline=None)
settings.register_profile("ci", max_examples=100, deadline=None)
settings.register_profile("nightly", max_examples=2000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.fixture(autouse=True)
def _isolated_git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may inherit the repository location of the git hook that runs the suite."""
    scrub_git_environment(monkeypatch)
