from base64 import urlsafe_b64encode
from typing import cast

import msgpack

from .models import Comment, Discussion, EntityGist
from app.setup import gh

DISCUSSION_QUERY = """
query getDiscussion($number: Int!, $org: String!, $repo: String!) {
  repository(owner: $org, name: $repo) {
    discussion(number: $number) {
      title
      number
      user: author { login }
      created_at: createdAt
      html_url: url
      answered: isAnswered
    }
  }
}
"""

DISCUSSION_COMMENT_QUERY = """
query getDiscussionComment($id: ID!) {
  node(id: $id) {
    ... on DiscussionComment {
      body
      author {
        name: login
        url
        icon_url: avatarUrl
      }
      created_at: createdAt
      html_url: url
    }
  }
}
"""


async def get_discussion(org: str, name: str, number: int) -> Discussion:
    resp = await gh.graphql.arequest(
        DISCUSSION_QUERY, variables={"number": number, "org": org, "repo": name}
    )
    data = resp["repository"]["discussion"]
    return Discussion(**data)


async def get_discussion_comment(id_: int, entity_gist: EntityGist) -> Comment:
    packed = cast(bytes, msgpack.packb([0, 0, id_]))
    node_id = "DC_" + urlsafe_b64encode(packed).decode().rstrip("=")

    resp = await gh.graphql.arequest(
        DISCUSSION_COMMENT_QUERY, variables={"id": node_id}
    )
    return Comment(**resp["node"], entity_gist=entity_gist)
