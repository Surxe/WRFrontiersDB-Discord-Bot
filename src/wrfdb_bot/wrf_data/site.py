"""Links to object pages on the WRFrontiersDB Site.

"Slug" here means only what the Site means by it: the URL path segment of an
object's page. The bot never generates slugs; it reads the Site's slug map
(id -> slug) and builds links from it.
"""

import json
import urllib.request
from pathlib import Path

from .object_types import ObjectType

SlugMap = dict[str, str]

FETCH_TIMEOUT_SECONDS = 30


def load_slug_map(source: str) -> SlugMap:
    """Load the Site's slug map from a URL or a file path."""
    if source.startswith(('http://', 'https://')):
        request = urllib.request.Request(source, headers={'User-Agent': 'wrfdb-bot'})
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            return json.load(response)
    with Path(source).open(encoding='utf-8') as f:
        return json.load(f)


class SiteLinks:
    def __init__(self, site_url: str, slug_map: SlugMap):
        self.site_url = site_url.rstrip('/')
        self.slug_map = slug_map

    def page_url(self, object_type: ObjectType, object_id: str) -> str | None:
        """URL of an object's Site page, or None if the Site has no slug for it yet."""
        if object_type.routed_by_id:
            path_segment = object_id
        else:
            path_segment = self.slug_map.get(object_id)
            if not path_segment:
                return None
        return f'{self.site_url}/{object_type.site_route}/{path_segment}/'
