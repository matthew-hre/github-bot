import datetime as dt
import re
from typing import Annotated, Literal, NamedTuple

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, field_validator

PASCAL_CASE_WORD_BOUNDARY = re.compile(r"([a-z])([A-Z])")


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
    name: str = Field(alias="login")
    url: str = Field(validation_alias=AliasChoices("url", "html_url"))
    icon_url: str = Field(validation_alias=AliasChoices("icon_url", "avatar_url"))


class Entity(BaseModel):
    number: int
    title: str
    body: str
    html_url: str
    user: GitHubUser
    created_at: dt.datetime

    @property
    def kind(self) -> str:
        return PASCAL_CASE_WORD_BOUNDARY.sub(r"\1 \2", type(self).__name__)


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


class Comment(BaseModel):
    author: GitHubUser
    body: str
    entity: Entity
    entity_gist: EntityGist
    created_at: dt.datetime
    html_url: str
    kind: str = "Comment"
    color: int | None = None

    @field_validator("body")
    @classmethod
    def _truncate_body(cls, value: str) -> str:
        if len(value) <= 4096:
            return value
        return value[:4090] + " [...]"
