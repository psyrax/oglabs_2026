# Prettier Data Posts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give data-heavy oglabs posts a wider layout, embeddable lazy-loaded JS charts (Plotly / Vega-Lite / D3), and an MCP `upload_image` tool, with the MCP self-describing these capabilities.

**Architecture:** Opt-in `Wide: true` frontmatter flag adds an `article--wide` class; CSS keeps prose at 700px but breaks tables/figures/images/charts out to ~1100px. A `<script type="module">` in `base.html` (next to the existing Mermaid loader) scans rendered code blocks for `@plotly` / `@vega-lite` / `@d3` markers and lazily imports the relevant library from a CDN, rendering into a `figure.chart`. A new `upload_image` MCP tool writes base64 images into `content/images/`, optimizes them, and returns a markdown snippet.

**Tech Stack:** Pelican + Jinja2 templates, vanilla CSS, ES module dynamic `import()` from esm.sh (Plotly, vega-embed, D3), Python MCP server (FastMCP), pytest.

**Conventions:** Run Python/make via the `oglabs` conda env (`source /opt/anaconda/etc/profile.d/conda.sh && conda activate oglabs`). `style.css` and `base.html` have pre-existing uncommitted local edits — **append** new rules/blocks; never rewrite the files. The Docker host is the content source of truth; deploy is in the final task.

---

### Task 1: Wide layout — `Wide: true` flag + breakout CSS

**Files:**
- Modify: `themes/oglabs/templates/article.html` (the `<article class="article">` line, ~line 62)
- Modify: `themes/oglabs/static/css/style.css` (append at end of file)

- [ ] **Step 1: Add the `article--wide` class toggle in the template**

In `themes/oglabs/templates/article.html`, change:

```html
  <article class="article">
```
to:
```html
  <article class="article{% if article.wide|default('')|lower == 'true' %} article--wide{% endif %}">
```

- [ ] **Step 2: Append the breakout CSS**

Append to the end of `themes/oglabs/static/css/style.css`:

```css
/* ---- Wide data posts (frontmatter `Wide: true`) ---------------------------
   Prose stays at the 700px column; data blocks break out to ~1100px.
   Breakout technique works from the narrow column via translateX. */
.article--wide .article__content table,
.article--wide .article__content figure,
.article--wide .article__content p:has(> img:only-child) {
  width: min(1100px, 92vw);
  max-width: none;
  margin-left: 50%;
  transform: translateX(-50%);
}
```

- [ ] **Step 3: Build with a wide fixture and verify the class + breakout markup**

```bash
cd /Code/oglabs && source /opt/anaconda/etc/profile.d/conda.sh && conda activate oglabs
cat > content/blog/_zz-wide-fixture.md <<'EOF'
Title: Wide fixture
Date: 2026-06-13
Category: blog
Slug: zz-wide-fixture
Wide: true

| a | b | c |
|---|---|---|
| 1 | 2 | 3 |
EOF
make slides >/dev/null 2>&1
pelican content -s pelicanconf.py -o output 2>&1 | tail -1
grep -o 'class="article article--wide"' output/blog/zz-wide-fixture/index.html
```
Expected: prints `class="article article--wide"` (flag applied). A non-wide post (e.g. an existing one) must still render `class="article"` only:
```bash
grep -o 'class="article[^"]*"' output/blog/por-que-homelab/index.html
```
Expected: `class="article"` (no `--wide`).

- [ ] **Step 4: Remove the fixture and commit**

```bash
rm -f content/blog/_zz-wide-fixture.md && rm -rf output/blog/zz-wide-fixture
git add themes/oglabs/templates/article.html themes/oglabs/static/css/style.css
git commit -m "feat: opt-in wide layout for data posts (Wide: true)"
```

---

### Task 2: Lazy chart loader — Plotly / Vega-Lite / D3

**Files:**
- Modify: `themes/oglabs/templates/base.html` (add a new `<script type="module">` immediately after the existing Mermaid `</script>`, ~line 52)
- Modify: `themes/oglabs/static/css/style.css` (append)

- [ ] **Step 1: Add the chart-loader script**

In `themes/oglabs/templates/base.html`, immediately after the closing `</script>` of the existing Mermaid block (before `<nav class="site-nav">`), insert:

```html
<script type="module">
  // Lazy chart loader: render @plotly / @vega-lite / @d3 fenced blocks.
  // Pygments drops the fence language, so detect by a first-line marker
  // (same philosophy as the Mermaid loader above). Libraries load from a CDN
  // only when a matching block is present on the page.
  const cache = {};
  const load = (k, url) => (cache[k] ||= import(url));
  for (const code of document.querySelectorAll('div.highlight > pre > code')) {
    const text = code.textContent.replace(/\n$/, '');
    const nl = text.indexOf('\n');
    const marker = (nl === -1 ? text : text.slice(0, nl)).trim();
    const body = nl === -1 ? '' : text.slice(nl + 1);
    if (!['@plotly', '@vega-lite', '@d3'].includes(marker)) continue;
    const fig = document.createElement('figure');
    fig.className = 'chart';
    const target = document.createElement('div');
    fig.appendChild(target);
    code.closest('div.highlight').replaceWith(fig);
    try {
      if (marker === '@plotly') {
        const Plotly = (await load('plotly', 'https://esm.sh/plotly.js-dist-min@2.35')).default;
        const spec = JSON.parse(body);
        Plotly.newPlot(target, spec.data || [], Object.assign({
          template: 'plotly_dark', paper_bgcolor: '#0d0d0d', plot_bgcolor: '#0d0d0d',
          font: { color: '#d4d4c8', family: 'JetBrains Mono, monospace' },
          margin: { t: 30, r: 20, b: 40, l: 50 },
        }, spec.layout || {}), { responsive: true, displayModeBar: false });
      } else if (marker === '@vega-lite') {
        const vegaEmbed = (await load('vega', 'https://esm.sh/vega-embed@6')).default;
        await vegaEmbed(target, JSON.parse(body), { theme: 'dark', actions: false, renderer: 'svg' });
      } else if (marker === '@d3') {
        const d3 = await load('d3', 'https://esm.sh/d3@7');
        new Function('container', 'd3', body)(target, d3);
      }
    } catch (e) {
      target.innerHTML = '<pre style="color:#f88">Chart error: ' + (e && e.message) + '</pre>';
    }
  }
</script>
```

- [ ] **Step 2: Append chart container CSS**

Append to the end of `themes/oglabs/static/css/style.css`:

```css
/* ---- Embedded charts ------------------------------------------------------ */
.article__content figure.chart {
  margin: 2rem 0;
  background: #0d0d0d;
}
.article__content figure.chart > div {
  width: 100%;
  min-height: 320px;
}
```

- [ ] **Step 3: Build a chart fixture and verify the blocks become `figure.chart` containers**

The markers render as plain code blocks server-side (the JS upgrades them in the browser), so verify the markers reach the output and the loader script is present:

```bash
cd /Code/oglabs && source /opt/anaconda/etc/profile.d/conda.sh && conda activate oglabs
cat > content/blog/_zz-chart-fixture.md <<'EOF'
Title: Chart fixture
Date: 2026-06-13
Category: blog
Slug: zz-chart-fixture
Wide: true

```
@vega-lite
{"mark":"bar","data":{"values":[{"x":"a","y":3},{"x":"b","y":5}]},"encoding":{"x":{"field":"x","type":"nominal"},"y":{"field":"y","type":"quantitative"}}}
```
EOF
make slides >/dev/null 2>&1
pelican content -s pelicanconf.py -o output 2>&1 | tail -1
grep -c '@vega-lite' output/blog/zz-chart-fixture/index.html
grep -c "esm.sh/vega-embed" output/blog/zz-chart-fixture/index.html
```
Expected: first grep ≥ 1 (marker present in the rendered code block), second grep = 1 (loader script present on the page).

- [ ] **Step 4: Manual browser check (charts actually render)**

Run the run skill or a local server and open the fixture in a browser; confirm the Vega bar chart renders dark and that, in a `Wide: true` post, the `figure.chart` breaks out wider than the prose. (Charts need a browser — the build only emits the markers.)

```bash
cd /Code/oglabs && python -m http.server 8001 -d output
# open http://localhost:8001/blog/zz-chart-fixture/ and confirm the bar chart renders
```

- [ ] **Step 5: Remove the fixture and commit**

```bash
rm -f content/blog/_zz-chart-fixture.md && rm -rf output/blog/zz-chart-fixture
git add themes/oglabs/templates/base.html themes/oglabs/static/css/style.css
git commit -m "feat: lazy-loaded Plotly/Vega-Lite/D3 chart blocks"
```

---

### Task 3: `upload_image` MCP tool (TDD)

**Files:**
- Modify: `mcp_server.py` (add constants + `_safe_image_filename` helper + `upload_image` tool; place after `read_post`)
- Test: `tests/test_mcp_server.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mcp_server.py`:

```python
import base64


def test_upload_image_writes_and_returns_markdown(repo, mocker):
    mocker.patch("mcp_server._run", return_value={"ok": True})
    data = base64.b64encode(b"\x89PNGfake").decode()
    out = mcp_server.upload_image(data, "umap.png", alt="UMAP")
    assert (repo / "content/images/umap.png").read_bytes() == b"\x89PNGfake"
    assert out["markdown"] == "![UMAP](/images/umap.png)"
    assert out["path"] == "content/images/umap.png"


def test_upload_image_rejects_traversal(repo):
    data = base64.b64encode(b"x").decode()
    with pytest.raises(ValueError, match="Invalid"):
        mcp_server.upload_image(data, "../secret.png")


def test_upload_image_rejects_bad_extension(repo):
    data = base64.b64encode(b"x").decode()
    with pytest.raises(ValueError, match="extension"):
        mcp_server.upload_image(data, "evil.exe")


def test_upload_image_rejects_bad_base64(repo):
    with pytest.raises(ValueError, match="base64"):
        mcp_server.upload_image("not base64!!!", "x.png")


def test_upload_image_rejects_oversize(repo, mocker):
    mocker.patch.object(mcp_server, "MAX_IMAGE_BYTES", 4)
    data = base64.b64encode(b"toolong").decode()
    with pytest.raises(ValueError, match="exceeds"):
        mcp_server.upload_image(data, "x.png")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /Code/oglabs && source /opt/anaconda/etc/profile.d/conda.sh && conda activate oglabs
python -m pytest tests/test_mcp_server.py -k upload_image -q
```
Expected: FAIL (`AttributeError: module 'mcp_server' has no attribute 'upload_image'`).

- [ ] **Step 3: Implement the tool**

In `mcp_server.py`, add the imports near the top (with the other stdlib imports):

```python
import base64
import binascii
```

Add module constants near `CONTENT_SECTIONS`:

```python
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
```

Add the helper near `_safe_slug`:

```python
def _safe_image_filename(name: str) -> str:
    """Reject path separators / traversal and non-image extensions."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or ".." in name:
        raise ValueError(f"Invalid filename {name!r}.")
    if Path(name).suffix.lower() not in ALLOWED_IMAGE_EXT:
        raise ValueError(
            f"Unsupported image extension. Use one of {sorted(ALLOWED_IMAGE_EXT)}."
        )
    return name
```

Add the tool after `read_post`:

```python
@mcp.tool()
def upload_image(
    data_base64: str, filename: str, alt: str = "", optimize: bool = True
) -> dict:
    """Save a base64-encoded image into content/images/ for use in posts.

    Writes content/images/<filename>, runs the image optimizer, and returns a
    ready-to-paste markdown snippet. Reference it in a post as the returned
    `markdown`. Use a descriptive filename (e.g. "umap-clusters.png").
    """
    name = _safe_image_filename(filename)
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("data_base64 is not valid base64.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds {MAX_IMAGE_BYTES} bytes.")
    path = _repo_path("content", "images", name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    result = _run(["python", "scripts/optimize_images.py"]) if optimize else None
    return {
        "path": f"content/images/{name}",
        "markdown": f"![{alt}](/images/{name})",
        "optimize": result,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_mcp_server.py -k upload_image -q
```
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full MCP suite + commit**

```bash
python -m pytest tests/test_mcp_server.py -q
git add mcp_server.py tests/test_mcp_server.py
git commit -m "feat(mcp): add upload_image tool"
```
Expected: all green.

---

### Task 4: MCP self-description — guide, instructions, `data_post` prompt, docs

**Files:**
- Modify: `mcp_server.py` (`WORKFLOW_GUIDE`, `SERVER_INSTRUCTIONS`, add `data_post` prompt)
- Test: `tests/test_mcp_server.py` (append)
- Create: `docs/data-posts.md`
- Modify: `docs/mcp-server.md` (tool list + link)

- [ ] **Step 1: Write the failing test for the prompt**

Append to `tests/test_mcp_server.py`:

```python
def test_data_post_prompt_mentions_wide_and_charts():
    text = mcp_server.data_post("clusters de audio")
    assert "clusters de audio" in text
    assert "Wide: true" in text
    assert "@plotly" in text and "upload_image" in text
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd /Code/oglabs && source /opt/anaconda/etc/profile.d/conda.sh && conda activate oglabs
python -m pytest tests/test_mcp_server.py -k data_post -q
```
Expected: FAIL (`has no attribute 'data_post'`).

- [ ] **Step 3: Extend the workflow guide and add the `data_post` prompt**

In `mcp_server.py`, inside the `WORKFLOW_GUIDE` string, append before the closing `"""` (after the Sections paragraph):

```
Data posts (wide layout + charts + images)
  - Set `Wide: true` in the frontmatter to widen tables/figures/charts to ~1100px
    while prose stays readable.
  - Embed charts as fenced code blocks whose first line is a marker:
      @plotly      -> JSON { "data": [...], "layout": {...} }
      @vega-lite   -> a Vega-Lite JSON spec
      @d3          -> JS body; receives (container, d3)
    Libraries load lazily in the browser; nothing to install.
  - Add images with upload_image(data_base64, filename, alt) and paste the
    returned markdown.
```

In `SERVER_INSTRUCTIONS`, append one line before the closing `"""`:

```
Data posts: set `Wide: true`, embed charts via @plotly/@vega-lite/@d3 fenced
blocks, and add images with upload_image. See the data_post prompt or guide().
```

Add the prompt next to `publish_blog_post`:

```python
@mcp.prompt()
def data_post(tema: str) -> str:
    """Guided workflow for an agent to build a data-heavy oglabs post (wide
    layout + charts + images). `tema` is the topic."""
    return (
        f"## Tarea: armar un post de DATA en oglabs vía su MCP\n\n"
        f"**Tema:** {tema}\n\n"
        f"{WORKFLOW_GUIDE}\n"
        "Para este post: poné `Wide: true` en el frontmatter; usá bloques "
        "@plotly / @vega-lite / @d3 para los gráficos; subí PNGs (matplotlib, "
        "etc.) con upload_image y pegá el markdown que devuelve. Estudiá el "
        "estilo con list_posts/read_post, y DETENTE para confirmar antes de "
        "cualquier paso de producción."
    )
```

- [ ] **Step 4: Run the prompt test + full suite**

```bash
python -m pytest tests/test_mcp_server.py -q
```
Expected: all green (the new `data_post` test passes).

- [ ] **Step 5: Write `docs/data-posts.md`**

Create `docs/data-posts.md`:

````markdown
# Data posts: wide layout, charts, and images

## Wide layout

Add `Wide: true` to the frontmatter. Prose stays at 700px; tables, figures,
images and charts break out to ~1100px on desktop.

```
Title: ...
Date: ...
Category: blog
Slug: ...
Wide: true
```

## Charts (lazy-loaded, no install)

Write a fenced code block whose **first line is a marker**. The library loads in
the browser only when used.

### Plotly — `@plotly` + `{ data, layout }`

```
@plotly
{"data":[{"type":"bar","x":["a","b","c"],"y":[3,5,2]}],"layout":{"title":"Demo"}}
```

### Vega-Lite — `@vega-lite` + a Vega-Lite spec

```
@vega-lite
{"mark":"line","data":{"values":[{"x":1,"y":2},{"x":2,"y":5}]},"encoding":{"x":{"field":"x","type":"quantitative"},"y":{"field":"y","type":"quantitative"}}}
```

### D3 — `@d3` + JS (receives `container`, `d3`)

```
@d3
const svg = d3.select(container).append("svg").attr("width", 600).attr("height", 200);
svg.append("circle").attr("cx", 80).attr("cy", 80).attr("r", 40).attr("fill", "#7dd3fc");
```

Charts render inside a `figure.chart` and participate in the wide breakout.

## Images

Use the MCP `upload_image(data_base64, filename, alt)` tool. It writes the file
into `content/images/`, optimizes it, and returns a markdown snippet like
`![alt](/images/<filename>)` to paste into the post.
````

- [ ] **Step 6: Update `docs/mcp-server.md`**

In `docs/mcp-server.md`, add `upload_image` to the Content tool list line, and add this line after the Discovery bullet:

```markdown
See `docs/data-posts.md` for wide-layout, chart, and image conventions. The
`data_post(tema)` prompt walks an agent through building a data post.
```

- [ ] **Step 7: Commit**

```bash
git add mcp_server.py tests/test_mcp_server.py docs/data-posts.md docs/mcp-server.md
git commit -m "feat(mcp): document data-post capabilities + data_post prompt"
```

---

### Task 5: Integration verification + deploy

**Files:** none (verification + ops)

- [ ] **Step 1: Full local build with a combined fixture**

```bash
cd /Code/oglabs && source /opt/anaconda/etc/profile.d/conda.sh && conda activate oglabs
cat > content/blog/_zz-data-demo.md <<'EOF'
Title: Data demo
Date: 2026-06-13
Category: blog
Slug: zz-data-demo
Wide: true

Texto de prosa angosta.

| cluster | n | valence |
|---------|---|---------|
| a | 231 | 0.21 |

```
@plotly
{"data":[{"type":"bar","x":["a","b"],"y":[3,5]}],"layout":{}}
```
EOF
make build 2>&1 | tail -3
grep -o 'class="article article--wide"' output/blog/zz-data-demo/index.html
python -m http.server 8001 -d output  # open http://localhost:8001/blog/zz-data-demo/, confirm wide table + Plotly chart
```
Expected: build succeeds; wide class present; in the browser the table is wide and the Plotly bar chart renders dark. Then remove the fixture:
```bash
rm -f content/blog/_zz-data-demo.md && rm -rf output/blog/zz-data-demo
```

- [ ] **Step 2: Merge the feature branch to master**

```bash
cd /Code/oglabs
git checkout master && git merge --no-ff <feature-branch> -m "Merge: prettier data posts (wide layout, charts, upload_image)"
```

- [ ] **Step 3: Deploy code to the host (targeted rsync, no --delete)**

```bash
rsync -R themes/oglabs/templates/article.html themes/oglabs/templates/base.html \
  themes/oglabs/static/css/style.css mcp_server.py \
  docs/data-posts.md docs/mcp-server.md \
  root@192.168.50.113:/mnt/user/appdata/oglabs/
```

- [ ] **Step 4: Rebuild/publish the site and restart the MCP**

```bash
ssh root@192.168.50.113 'docker exec -w /app oglabs-mcp make publish 2>&1 | tail -5 && docker restart oglabs-mcp >/dev/null && echo MCP_RESTARTED'
```
Expected: `make publish` reaches the CloudFront invalidation (build OK), then `MCP_RESTARTED`.

- [ ] **Step 5: Verify live**

```bash
ssh root@192.168.50.113 'docker exec oglabs-mcp python -c "import asyncio,mcp_server as m; print(\"upload_image\" in [t.name for t in asyncio.run(m.mcp.list_tools())]); print(\"data_post\" in [p.name for p in asyncio.run(m.mcp.list_prompts())])"'
```
Expected: `True` and `True`. (The wide layout/charts only affect posts that opt in, so existing posts are unchanged.)

---

## Notes

- `generate_image` (AI image generation) is intentionally **out of scope** (deferred spec).
- esm.sh CDN is used for the chart libraries; if the homelab must avoid third-party CDNs, a follow-up can vendor the libs under `content/` and point the loader at local paths.
- The wide breakout relies on CSS `:has()` (broad browser support since 2023).
