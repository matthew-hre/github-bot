from unittest.mock import Mock

import discord
import pytest

from app.utils import Account, is_dm


@pytest.mark.parametrize(
    ("type_", "result"), [(discord.Member, False), (discord.User, True)]
)
def test_is_dm(*, type_: type[Account], result: bool) -> None:
    assert is_dm(Mock(type_)) == result
