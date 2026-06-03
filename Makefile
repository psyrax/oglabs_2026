# Load .env if it exists
-include .env
export

# Unraid host running the MCP container (override on the CLI if needed)
MCP_HOST ?= root@192.168.50.113
MCP_REPO_PATH ?= /mnt/user/appdata/oglabs
MCP_IMAGE ?= oglabs-mcp:latest
MCP_CONTAINER ?= oglabs-mcp

.PHONY: photos images build deploy publish clean strip-fences mcp sync-host

# Process new gallery photos (skips already-processed via manifest)
photos:
	python scripts/photo_pipeline.py

# Optimize new post images (skips already-processed via manifest)
images:
	python scripts/optimize_images.py

# Strip ```markdown fences and <think> tags from generated content
strip-fences:
	python scripts/strip_fences.py

# Full build: process photos + images, strip LLM artifacts, then run Pelican
build: photos images strip-fences
	pelican content -s pelicanconf.py -o output

# Deploy to S3 and optionally invalidate CloudFront cache
deploy:
	@test -n "$(S3_BUCKET)" || (echo "ERROR: S3_BUCKET is not set"; exit 1)
	aws s3 sync output/ s3://$(S3_BUCKET)/ --delete
	@if [ -n "$(CLOUDFRONT_DISTRIBUTION_ID)" ]; then \
		echo "Invalidating CloudFront cache..."; \
		aws cloudfront create-invalidation --distribution-id $(CLOUDFRONT_DISTRIBUTION_ID) --paths "/*"; \
	fi

# Build + deploy in one step
publish: build deploy

# Remove generated output
clean:
	rm -rf output/

# Create a new draft: make draft SECTION=blog TITLE="Mi post"
draft:
	@test -n "$(SECTION)" || (echo "ERROR: SECTION is not set (blog or projects)"; exit 1)
	@test -n "$(TITLE)" || (echo "ERROR: TITLE is not set"; exit 1)
	@SLUG=$$(echo "$(TITLE)" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$$//g'); \
	FILE="drafts/$(SECTION)/$$SLUG.md"; \
	DATE=$$(date +%Y-%m-%d); \
	printf "Title: $(TITLE)\nDate: $$DATE\nCategory: $(SECTION)\nSlug: $$SLUG\n\n" > $$FILE; \
	echo "Created $$FILE"

# Run the MCP server in the foreground (local dev; Docker is used in prod)
mcp:
	python mcp_server.py

# Sync this repo to the Unraid host, rebuild the image, and restart the container.
# Override host/path with: make sync-host MCP_HOST=root@host MCP_REPO_PATH=/path
sync-host:
	rsync -az --delete \
		--exclude='.git/' \
		--exclude='.env' \
		--exclude='output/' \
		--exclude='photos/originals/' \
		--exclude='.playwright-mcp/' \
		--exclude='__pycache__/' \
		--exclude='.pytest_cache/' \
		--exclude='*.pyc' \
		--exclude='diag-*.png' \
		--exclude='slide-*.png' \
		--exclude='slides-*.png' \
		./ $(MCP_HOST):$(MCP_REPO_PATH)/
	ssh $(MCP_HOST) 'cd $(MCP_REPO_PATH) && \
		docker build -t $(MCP_IMAGE) . && \
		docker rm -f $(MCP_CONTAINER) 2>/dev/null; \
		docker run -d \
			--name $(MCP_CONTAINER) \
			--network bridge \
			-p 8765:8765 \
			-v $(MCP_REPO_PATH):/app \
			--env-file $(MCP_REPO_PATH)/.env \
			-e OGLABS_MCP_PORT=8765 \
			--restart unless-stopped \
			$(MCP_IMAGE) && \
		docker ps --filter name=$(MCP_CONTAINER) --format "{{.Names}}  {{.Status}}  {{.Ports}}"'
