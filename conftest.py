"""Shared test setup."""

import pytest

_GIT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


@pytest.fixture(autouse=True)
def clean_git_env(monkeypatch):
    """A git hook exports GIT_* variables. Tests that make their own
    repositories must not inherit them, or git writes to the outer
    repository's index."""
    for key in _GIT_VARS:
        monkeypatch.delenv(key, raising=False)
