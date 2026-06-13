"""Pelican plugin: auto-tag World Cup project posts.

Any article in the `projects` category whose title mentions the Mundial gets the
`mundial` tag at build time, so it shows up in the /projects/mundial/ subsection
without the tag having to be written into the source frontmatter. Idempotent and
retroactive — every matching post (existing or new) is tagged on each build.
"""
import re

from pelican import signals
from pelican.urlwrappers import Tag

_MUNDIAL_RE = re.compile(r"mundial|world cup|copa del mundo", re.IGNORECASE)


def _autotag(content):
    category = getattr(content, "category", None)
    if category is None or category.name != "projects":
        return
    if not _MUNDIAL_RE.search(content.title or ""):
        return
    tags = list(getattr(content, "tags", None) or [])
    if any(getattr(t, "name", "").lower() == "mundial" for t in tags):
        return
    tags.append(Tag("mundial", content.settings))
    content.tags = tags


def register():
    signals.content_object_init.connect(_autotag)
