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

## Connect a remote agent

Point the agent's MCP client at:

    http://192.168.50.113:8765/mcp

Transport: streamable-HTTP. No authentication (LAN only).

## Tools

- Content: `list_drafts`, `list_posts`, `read_post`, `create_draft`, `write_draft`
- Pipeline: `improve_writing`, `optimize_images`, `process_photos`
- Build/deploy: `build`, `deploy`, `publish`

`read_post` is restricted to `.md` files under `drafts/` or `content/`.
`deploy`/`publish` push to production S3 and invalidate CloudFront — any agent
that can reach the server can trigger them (no auth by design; LAN only).

## Local dev (no Docker)

    conda run -n oglabs make mcp
