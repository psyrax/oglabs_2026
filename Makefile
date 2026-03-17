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

# Deploy to S3 (S3_BUCKET must be set)
deploy:
	aws s3 sync output/ s3://$(S3_BUCKET)/ --delete

# Build + deploy in one step
publish: build deploy

# Remove generated output
clean:
	rm -rf output/
