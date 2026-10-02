"""Finding `[[queries]]` in message text."""

import re

MAX_QUERIES_PER_MESSAGE = 5
MAX_QUERY_LENGTH = 100

_CODE_BLOCK = re.compile(r'```.*?```', re.DOTALL)
_INLINE_CODE = re.compile(r'`[^`\n]*`')
_QUERY = re.compile(r'\[\[([^\[\]\n]+?)\]\]')


def extract_queries(content: str) -> list[str]:
    """The distinct `[[...]]` queries in a message, in order, at most MAX_QUERIES_PER_MESSAGE.

    Text inside code blocks and inline code is ignored, so people can show the syntax.
    """
    content = _INLINE_CODE.sub('', _CODE_BLOCK.sub('', content))
    queries: list[str] = []
    for match in _QUERY.finditer(content):
        query = ' '.join(match.group(1).split())
        if not query or len(query) > MAX_QUERY_LENGTH or query.lower() in (q.lower() for q in queries):
            continue
        queries.append(query)
        if len(queries) == MAX_QUERIES_PER_MESSAGE:
            break
    return queries


def split_type_prefix(query: str) -> tuple[str | None, str]:
    """`talent: Vanguard` -> (`talent`, `Vanguard`); no colon -> (None, query).

    Whether the prefix names a real type is up to the caller.
    """
    prefix, colon, name = query.partition(':')
    if not colon or not prefix.strip() or not name.strip():
        return None, query.strip()
    return prefix.strip(), name.strip()
