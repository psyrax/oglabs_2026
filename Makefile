# Load .env if it exists
-include .env
export

.PHONY: photos images build deploy publish clean

# Process new gallery photos (skips already-processed via manifest)
photos:
	python scripts/photo_pipeline.py

# Optimize new post images (skips already-processed via manifest)
images:
	python scripts/optimize_images.py

# Full build: process photos + images, then run Pelican
build: photos images
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
