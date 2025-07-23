from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.common.hooks import MessageLinker, create_delete_hook

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord as dc

    type DeleteHook = Callable[[dc.Message], Awaitable[None]]

linker = pytest.fixture(lambda: MessageLinker())


@pytest.fixture
def delete_hook(linker: MessageLinker) -> DeleteHook:
    return create_delete_hook(linker=linker)
