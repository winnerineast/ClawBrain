# Generated from design/docker.md v1.0
FROM python:3.12-slim

WORKDIR /app

# 依赖层（源码变动不触发重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY src/ ./src/

# 非 root 用户运行
RUN useradd -u 1000 -m clawbrain && \
    mkdir -p /app/data/blobs && \
    chown -R clawbrain:clawbrain /app

USER clawbrain

EXPOSE 11435

# workers=1: 保证 in-memory WorkingMemory 会话状态在单进程内一致
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "11435", "--workers", "1"]
