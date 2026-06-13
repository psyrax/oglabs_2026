import os

SITENAME = 'oglabs'
SITEURL = os.getenv('SITEURL', '')

PATH = 'content'

TIMEZONE = 'America/Argentina/Buenos_Aires'
DEFAULT_LANG = 'es'

THEME = 'themes/oglabs'

# Content paths
ARTICLE_PATHS = ['blog', 'projects', 'photos']
ARTICLE_EXCLUDE_PATHS = ['photos/images']

# URL structure
ARTICLE_URL = '{category}/{slug}/'
ARTICLE_SAVE_AS = '{category}/{slug}/index.html'

CATEGORY_URL = '{slug}/'
CATEGORY_SAVE_AS = '{slug}/index.html'

# Static assets: fotos de galería + imágenes de posts de blog/proyectos
STATIC_PATHS = ['photos/images', 'images', 'slides']

# Pages (section landing pages like /projects/mundial/)
PAGE_PATHS = ['pages']
PAGE_URL = '{slug}/'
PAGE_SAVE_AS = '{slug}/index.html'

# Tags are used only to group posts in custom templates; the theme has no
# tag/author templates, so disable those auto-generated pages.
TAG_SAVE_AS = ''
TAGS_SAVE_AS = ''
AUTHOR_SAVE_AS = ''
AUTHORS_SAVE_AS = ''

# Delete stale files from output on each build
DELETE_OUTPUT_DIRECTORY = True

# Feed settings (disabled for v1)
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Pagination
DEFAULT_PAGINATION = False
