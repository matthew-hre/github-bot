import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field


def state_validator(value: object) -> bool:
    match value:
        case bool():
            return value
        case "open" | "closed":
            return value == "closed"
        case _:
            msg = "`closed` must be a bool or a string of 'open' or 'closed'"
            raise ValueError(msg)


class GitHubUser(BaseModel):
    login: str


class Entity(BaseModel):
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
