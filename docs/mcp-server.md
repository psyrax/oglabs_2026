# oglabs MCP server

Exposes oglabs blog operations over MCP (streamable-HTTP) for remote agents
on the LAN.

## Run (Unraid / Docker)

Docker runs on the Unraid host (`192.168.50.113`).

1. Put the repo on the Unraid host. Set `OGLABS_REPO_PATH` to its path
   (or run `docker compose` from inside the repo).
2. Ensure `.env` has the LLM keys and AWS credentials:
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`,
   plus the existing `S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`,
   `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY` (if using the Claude backend).
3. Build and start:

   ```bash
   OGLABS_REPO_PATH=/path/to/oglabs docker compose up -d --build
   ```

The server listens on `0.0.0.0:8765`.

## Run (Unraid native Docker UI)

To manage the container from Unraid's **Docker** tab instead of compose:

1. Copy the repo to the host (e.g. `/mnt/user/appdata/oglabs`) and ensure `.env`
   is present with LLM + AWS credentials.
2. Build the image on the host (the template references a local tag, it does not
   pull from a registry):

   ```bash
   docker build -t oglabs-mcp:latest /mnt/user/appdata/oglabs
   ```

3. Install the template:

   ```bash
   cp unraid/my-oglabs-mcp.xml /boot/config/plugins/dockerMan/templates-user/
   ```

4. In the Unraid UI: **Docker → Add Container → Template: oglabs-mcp**. Adjust the
   "Repo path" if the repo lives elsewhere, then **Apply**.

Notes:
- Credentials are not in the template — `make`/the scripts read them from the
  `.env` inside the mounted repo.
- Don't use "Force update / check for updates" on this container: the image is
  local, so a pull would fail. Rebuild with `docker build` after code changes,
  then restart the container.

## Connect a remote agent

Point the agent's MCP client at:

    http://192.168.50.113:8765/mcp

Transport: streamable-HTTP. No authentication (LAN only).

## Tools

- Content: `list_drafts`, `list_posts`, `read_post`, `create_draft`, `write_draft`, `publish_draft`, `delete_draft`
- Pipeline: `improve_writing`, `optimize_images`, `process_photos`
- Build/deploy: `build`, `deploy`, `publish`, `publish_draft_live`

`publish_draft_live(section, slug)` is the one-shot path: it promotes the draft to
`content/` and runs `make publish` (build + scrub + S3 + CloudFront) — i.e. draft to
production in a single call.

The site builds only from `content/`. Drafts written via `create_draft`/`write_draft`
land in `drafts/`; promote one with `publish_draft(section, slug)` (verbatim copy to
`content/`) before `build`. `deploy` runs `scripts/scrub_output.py` first, which
redacts high-confidence secrets and credential-style `NAME=value` assignments from
`output/` before the S3 sync (IP/path and email scrubbing are available but off by
default — toggles at the top of the script).

`read_post` is restricted to `.md` files under `drafts/` or `content/`.
`deploy`/`publish` push to production S3 and invalidate CloudFront — any agent
that can reach the server can trigger them (no auth by design; LAN only).

## Local dev (no Docker)

    conda run -n oglabs make mcp
