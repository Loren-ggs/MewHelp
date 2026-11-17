#!/usr/bin/env bash
# 轻量级一体化启动脚本 (Lite Mode: SQLite + LocalMilvusClient + 2台 MCP Server + FastAPI)
# 内存占用 < 250MB，无需安装 MySQL / Milvus / etcd / MinIO 容器，适合小内存服务器及免费云平台部署
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONUTF8=1
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# 默认使用轻量级本地 SQLite 与本地混合向量检索(如环境变量未显式指定)
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///data/mewhelp.db}"
export MILVUS_URI="${MILVUS_URI:-local://data/milvus_lite.json}"
PORT="${PORT:-8000}"

mkdir -p data log

# 选择 Python 运行器(容器内若已直接安装到系统或 .venv 则直接调,本地开发优先走 uv)
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
  UVICORN=".venv/bin/uvicorn"
elif command -v uv >/dev/null 2>&1; then
  PY="uv run python"
  UVICORN="uv run uvicorn"
else
  PY="python3"
  UVICORN="uvicorn"
fi

cleanup() {
  echo "正在停止 MCP Server 子进程..."
  [ -n "${MCP_LOG_PID:-}" ] && kill "$MCP_LOG_PID" 2>/dev/null || true
  [ -n "${MCP_AFT_PID:-}" ] && kill "$MCP_AFT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "🚀 启动物流 MCP Server (:8101)..."
PORT=8101 $PY mcp_servers/logistics_server.py > log/mcp-logistics.log 2>&1 &
MCP_LOG_PID=$!

echo "🚀 启动售后 MCP Server (:8102)..."
PORT=8102 $PY mcp_servers/aftersales_server.py > log/mcp-aftersales.log 2>&1 &
MCP_AFT_PID=$!

# 等待两台 MCP Server 端口就绪
for port in 8101 8102; do
  for _ in $(seq 1 30); do
    if $PY -c "import socket; s=socket.socket(); s.settimeout(0.2); exit(s.connect_ex(('127.0.0.1', $port)))" 2>/dev/null; then
      break
    fi
    sleep 0.2
  done
done

echo "✅ MCP Server 已就绪 (:8101 / :8102)"
echo "🌟 启动 MewHelp 主服务 (http://0.0.0.0:${PORT}) [DB=${DATABASE_URL}, VECTOR=${MILVUS_URI}]..."
exec $UVICORN app.main:app --host 0.0.0.0 --port "${PORT}"
