import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def state_validator(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if not isinstance(v, str):
        msg = "`closed` must be a string or a bool"
        raise TypeError(msg)
    if v not in {"open", "closed"}:
        msg = "`closed` must be 'open' or 'closed'"
        raise ValueError(msg)
    return v == "closed"


class GitHubUser(BaseModel):
    login: str


class Entity(BaseModel):
    model_config = ConfigDict(extra="allow")

    number: int
    title: str
    html_url: str
    user: GitHubUser
    created_at: dt.datetime


class Issue(Entity):
    closed: Annotated[bool, Field(alias="state"), BeforeValidator(state_validator)]
    state_reason: Literal["completed", "not_planned", "duplicate", None]


class PullRequest(Entity):
    closed: Annotated[bool, Field(alias="state"), BeforeValidator(state_validator)]
    draft: bool
    merged: bool


class Discussion(Entity):
    answered: bool
