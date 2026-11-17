FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    DATABASE_URL=sqlite+aiosqlite:///data/mewhelp.db \
    MILVUS_URI=local://data/milvus_lite.json \
    PORT=8000

# 安装 uv 并同步项目运行依赖(不含训练重依赖组 ml)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY app ./app
COPY mcp_servers ./mcp_servers
COPY data/kb ./data/kb
COPY scripts ./scripts
COPY sql ./sql

RUN chmod +x scripts/start_lite.sh && mkdir -p data log

EXPOSE 8000

CMD ["bash", "scripts/start_lite.sh"]
