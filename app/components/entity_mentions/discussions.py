from .models import Discussion
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


async def get_discussion(org: str, name: str, number: int) -> Discussion:
    resp = await gh.graphql.arequest(
        DISCUSSION_QUERY, variables={"number": number, "org": org, "repo": name}
    )
    data = resp["repository"]["discussion"]
    return Discussion(**data)
