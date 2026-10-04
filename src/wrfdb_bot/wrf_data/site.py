"""Links to object pages on the WRFrontiersDB Site.

"Slug" here means only what the Site means by it: the URL path segment of an
object's page. The bot never generates slugs; it reads the slug map
(id -> slug) that WRFrontiersDB-Data publishes as `index/slug_map.json`, and
builds links from it.
"""

from .object_types import ObjectType

SlugMap = dict[str, str]


class SiteLinks:
    def __init__(self, site_url: str, slug_map: SlugMap):
        self.site_url = site_url.rstrip('/')
        self.slug_map = slug_map

    def page_url(self, object_type: ObjectType, object_id: str) -> str | None:
        """URL of an object's Site page, or None if it has no slug (no page)."""
        slug = self.slug_map.get(object_id)
        if not slug:
            return None
        return f'{self.site_url}/{object_type.site_route}/{slug}/'
