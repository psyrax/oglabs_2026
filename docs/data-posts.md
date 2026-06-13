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
