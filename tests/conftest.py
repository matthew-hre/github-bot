import os

import pytest

from tests.fixtures import bot_env, delete_hook, edit_hook, linker, safe_environ

__all__ = ("bot_env", "delete_hook", "edit_hook", "linker")


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    os.environ |= safe_environ()
