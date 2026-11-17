#!/usr/bin/env bash
# 阿里云 / 腾讯云 Ubuntu 24.04 (2C2G) 轻量一键部署脚本
# 作用: 开启 2G Swap 防内存抖动 -> 安装 uv(国内镜像加速) -> 同步依赖 -> 注册 systemd 守护进程开机自启
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== [1/5] 检查并配置 2GB Swap 虚拟内存 (保障 2G 服务器永不 OOM) ==="
if [ "$(swapon --show | wc -l)" -eq 0 ]; then
  if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
  fi
  sudo swapon /swapfile || true
  if ! grep -q "/swapfile" /etc/fstab; then
    echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
  fi
  echo "✅ 2GB Swap 已开启"
else
  echo "✅ 系统已有 Swap，跳过"
fi

echo "=== [2/5] 检查并安装 uv 包管理器 ==="
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  sudo apt-get update -y && sudo apt-get install -y curl git
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "=== [3/5] 使用国内镜像源同步 Python 依赖 ==="
export UV_INDEX_URL="${UV_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
uv sync --no-dev

echo "=== [4/5] 检查 .env 配置文件 ==="
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️ 已生成 .env 模板，请务必编辑 $PROJECT_DIR/.env 填入 CHAT_API_KEY / EMBED_API_KEY / RERANK_API_KEY！"
fi

chmod +x scripts/start_lite.sh
mkdir -p data log

echo "=== [5/5] 配置 systemd 后台常驻服务 (mewhelp.service) ==="
SERVICE_FILE="/etc/systemd/system/mewhelp.service"
USER_NAME="$(whoami)"
UV_BIN="$(command -v uv)"
USER_PATH="$(dirname "$UV_BIN"):/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=MewHelp AI Customer Service Agent (Lite Mode)
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${USER_PATH}"
Environment="PYTHONUTF8=1"
ExecStart=/bin/bash ${PROJECT_DIR}/scripts/start_lite.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mewhelp.service
sudo systemctl restart mewhelp.service

echo ""
echo "🎉 部署完成！"
echo "--------------------------------------------------------"
echo "1. 查看运行状态: sudo systemctl status mewhelp"
echo "2. 实时查看日志: journalctl -u mewhelp -f  或  tail -f log/app.log"
echo "3. 修改 .env 后重启: sudo systemctl restart mewhelp"
echo "4. 请确保阿里云控制台【安全组】已放行 TCP 8000 端口"
echo "--------------------------------------------------------"
