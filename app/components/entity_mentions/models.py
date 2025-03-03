import datetime as dt
from typing import Annotated, Literal, NamedTuple

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
    state_reason: Literal["completed", "reopened", "not_planned", "duplicate", None]


class PullRequest(Entity):
    closed: Annotated[bool, Field(alias="state"), BeforeValidator(state_validator)]
    draft: bool
    merged: bool


class Discussion(Entity):
    answered: bool


class EntityGist(NamedTuple):
    owner: str
    repo: str
    number: int

    def __str__(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


class CommentAuthor(BaseModel):
    name: str
    url: str
    icon_url: str


class Comment(BaseModel):
    author: CommentAuthor
    body: str
    entity_gist: EntityGist
    created_at: dt.datetime
    html_url: str
