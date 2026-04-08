# Generated from design/docker.md v1.0
FROM python:3.12-slim

WORKDIR /app

# Dependency layer (source code changes do not trigger re-installation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code
COPY src/ ./src/

# Run as non-root user
RUN useradd -u 1000 -m clawbrain && \
    mkdir -p /app/data/blobs && \
    chown -R clawbrain:clawbrain /app

USER clawbrain

EXPOSE 11435

# workers=1: ensures in-memory WorkingMemory session state consistency within a single process
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "11435", "--workers", "1"]
