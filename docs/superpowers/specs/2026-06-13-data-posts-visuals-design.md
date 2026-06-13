# Design: prettier data posts (wide layout + JS charts + image upload)

- **Date:** 2026-06-13
- **Status:** approved (design); ready for implementation plan
- **Author:** Psyrax + Claude

## Goal

Several oglabs posts are data-heavy (wide tables, plots). Make them look better:
a wider layout for data content, embeddable interactive JS charts, and an MCP
tool to upload post images — plus make the MCP self-describe these capabilities
so remote agents use them.

## Out of scope (deferred)

- **`generate_image`** (AI image generation via external API) — deferred to a
  later spec. Provider would be OpenAI `gpt-image-1` (pluggable), key in the host
  `.env`. Not built now.

## Constraints / context

- Pelican static site; the **Docker host is the source of truth for content**,
  local is the source for code/theme. Deploy = targeted rsync (no `--delete`) +
  `make publish` in the container; MCP code changes need a `docker restart`.
- The theme already lazy-loads **Mermaid** in `base.html` (scans rendered code
  blocks, loads the lib from CDN only when needed). Charts reuse this pattern.
- Content column is `max-width: 700px` (`.article`, `.article__content`).
- Dark theme (`#0d0d0d` bg, JetBrains Mono / serif).
- `style.css` and `base.html` have **pre-existing uncommitted local edits** (not
  from this work) that the implementation must edit around (append, don't clobber).

## Design

### 1. Wide layout for data posts (hybrid: opt-in flag + selective breakout)

- Frontmatter flag **`Wide: true`** on a post → `article.html` adds class
  `article--wide` to the article element.
- CSS: prose (paragraphs, headings, lists, blockquotes) stays at **700px**
  centered. Inside `.article--wide`, "wide blocks" — `table`, `figure`,
  `figure.chart`, and images — break out to **`min(1100px, 92vw)`**, centered via
  the standard breakout technique (`width: min(1100px,92vw); margin-left:50%;
  transform:translateX(-50%)`).
  - Markdown images render as `<img>` inside a `<p>`; target
    `.article--wide .article__content p:has(> img:only-child)` (and bare
    `figure`) for breakout. Charts are authored/emitted as `figure.chart`.
- Without the flag, rendering is **identical to today** (zero impact on existing
  posts). On mobile, `92vw` keeps everything within the viewport as now.

### 2. Embeddable JS charts: Plotly + D3 + Vega-Lite (lazy)

Extend the `base.html` loader so each library loads from CDN **only if the page
uses it**. Authoring is declarative for agent-friendliness:

- **Fenced blocks with a first-line marker** (robust; Pygments drops the fence
  language, so detection is content-based like Mermaid):
  - ` ```\n@plotly\n{ "data": [...], "layout": {...} }\n``` ` → `Plotly.newPlot`
    with a dark template default.
  - ` ```\n@vega-lite\n{ ...Vega-Lite spec... }\n``` ` → `vegaEmbed` with a dark
    config.
- **D3** escape hatch for bespoke viz: a ` ```\n@d3\n<js>\n``` ` block (the JS
  receives a target `<div>`), or raw HTML `<div class="d3-chart">` + `<script>`.
  D3 is lazy-loaded when a `@d3` block or `.d3-chart` is present.
- The loader scans `div.highlight > pre > code`, reads the first line; on a known
  marker it replaces the block with a `<figure class="chart">` container and
  renders into it. `figure.chart` participates in the wide breakout (§1).
- Dark theming consistent with the site (bg `#0d0d0d`, mono font, muted grid).
- **Alternative considered:** a Pelican/Markdown extension that rewrites
  `plotly`/`vega-lite` fences into `<div data-spec>` at build time. More robust
  but adds build complexity; the marker + client-side approach matches the
  existing Mermaid pattern and needs no build changes. Recommend the marker
  approach; revisit if detection proves brittle.

### 3. MCP tool: `upload_image`

- **`upload_image(data_base64: str, filename: str, alt: str = "") -> str`**
  - Validate `filename` (safe name, no path separators / traversal; allowed
    image extensions). Enforce a max decoded size.
  - Decode base64, write to `content/images/<filename>`.
  - Run the existing optimizer (`scripts/optimize_images.py`) so it is web-ready.
  - Return a ready-to-paste markdown snippet: `![<alt>](/images/<filename>)`.
- Mirrors the existing content-tool conventions (validation helpers, structured
  return). Unit tests mock the filesystem/optimizer; cover happy path, bad
  filename, oversize, bad base64.

### 4. MCP self-description ("the MCP has info of that")

- Update `WORKFLOW_GUIDE` + `SERVER_INSTRUCTIONS` to cover: the `Wide: true`
  flag, the chart blocks (one tiny example each), and `upload_image`.
- New doc **`docs/data-posts.md`**: copy-paste examples for the wide flag, each
  chart type, and image upload. Link it from `docs/mcp-server.md` (and add the
  new tool to the tool list).
- New MCP prompt **`data_post(tema)`**: guides an agent to build a data post
  (set `Wide: true`, use chart blocks, upload images), reusing the workflow guide.

## Files touched

- `themes/oglabs/templates/article.html` — `Wide` flag → `article--wide` class.
- `themes/oglabs/static/css/style.css` — `.article--wide` breakout + `.chart`
  figure styling (append; reconcile with pre-existing local edits).
- `themes/oglabs/templates/base.html` — extend the lazy chart/lib loader (append
  to the existing Mermaid script; reconcile with pre-existing local edits).
- `mcp_server.py` — `upload_image` tool; `data_post` prompt; guide/instructions.
- `tests/test_mcp_server.py` — `upload_image` tests.
- `docs/data-posts.md` (new), `docs/mcp-server.md` (update).

## Testing

- MCP: unit tests for `upload_image` (pytest, mirrors existing style; mock the
  optimizer call). Full suite must stay green.
- Layout/charts: local Pelican build with a fixture data post (`Wide: true` +
  one of each chart block + an image); verify the wide class, the chart
  containers render, and prose stays narrow. Manual browser check of the deck.

## Deployment

- Theme/CSS/templates + `pelicanconf` (if needed) + `mcp_server.py` + docs →
  rsync to host (no `--delete`); `make publish` in the container for the site;
  `docker restart oglabs-mcp` for the MCP. Verify live.

## Open questions (resolved)

- Layout: hybrid (flag + selective breakout). Width 1100px. ✅
- Libs: Plotly + D3 + Vega-Lite, lazy. ✅
- Image: upload now; generation deferred. ✅
