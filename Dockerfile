FROM python:3.12-slim

# make + awscli are needed by the build/deploy tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends make awscli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps in a cached layer (the repo itself is mounted at runtime)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8765
CMD ["python", "mcp_server.py"]
