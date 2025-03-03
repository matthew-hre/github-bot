from base64 import urlsafe_b64encode

from .models import Comment, Discussion, EntityGist
from app.setup import gh

DISCUSSION_QUERY = """
query getDiscussion($number: Int!, $org: String!, $repo: String!) {
  repository(owner: $org, name: $repo) {
    discussion(number: $number) {
      body
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
      discussion {
        body
        title
        number
        user: author { login }
        created_at: createdAt
        html_url: url
        answered: isAnswered
      }
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


def _encode_discussion_comment_id(comment_id: int) -> str:
    # Step one: encode it as a 32-bit integer in msgpack.
    # Discussion comment ids seem to always be large enough to need 32 bits,
    # but small enough to always fit in 32 bits.
    packed = b"\x93\x00\x00\xce" + comment_id.to_bytes(4, "big")
    #            ^   ^   ^    ^    ^
    #            |   |   |    |    The integer itself, in big-endian.
    #            |   |   |    `- Start 32-bit int.
    #            | This is 0 (positive fixint).
    # This is 0b10010011. fixarrays start with 0b1001XXXX, where XXXX is the
    # length of the array as a four-bit unsigned integer.

    # Step two: base-64 encode it, prefix it, and decode it to a `str`.
    return (b"DC_" + urlsafe_b64encode(packed)).decode()


async def get_discussion_comment(entity_gist: EntityGist, id_: int) -> Comment:
    node_id = _encode_discussion_comment_id(id_)
    resp = await gh.graphql.arequest(
        DISCUSSION_COMMENT_QUERY, variables={"id": node_id}
    )
    discussion = Discussion(**resp["node"].pop("discussion"))
    return Comment(
        **resp["node"],
        entity_gist=entity_gist,
        entity=discussion,
    )
