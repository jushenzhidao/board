# =============================================================================
# 渠道看板 —— 单镜像部署（nginx 静态托管 + 桥接服务同容器运行）
#
# 构建：  docker build -t channel-board:latest .
# 运行：  见 docker-compose.yml 或 docker run 命令（README「Docker 部署」）
#
# 架构：
#   nginx(80)  ->  / 静态资源(dist) + /sites.json、/channels/* (挂载卷)
#               ->  /ch/ 反代到 127.0.0.1:8123（dev_bridge.py 桥接）
#   桥接(8123)  ->  ClickHouse 原生 9000（按 X-Site 头路由多站点）
# =============================================================================

# ---------- Stage 1: 构建前端 ----------
FROM node:22-alpine AS web
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---------- Stage 2: 运行时 ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BRIDGE_HOST=127.0.0.1 \
    BRIDGE_PORT=8123

# nginx（静态 + 反代）与 supervisor（进程守护）
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app

# Python 依赖（clickhouse-driver 走原生 9000；pymysql 用于渠道同步/连接测试）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 前端构建产物
COPY --from=web /app/dist /app/dist

# 桥接与渠道同步脚本（同目录 import）
COPY scripts/dev_bridge.py /app/scripts/dev_bridge.py
COPY scripts/sync_channels.py /app/scripts/sync_channels.py

# 容器内 nginx / supervisor 配置
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/board.conf

# 挂载点（凭据与运行时生成物不入镜像，用 volume 持久化）：
#   /app/config  -> config/sites.json（CH/MySQL 凭据）
#   /app/public  -> public/sites.json + public/channels/*.json（渠道映射）
RUN mkdir -p /app/config /app/public/channels
VOLUME ["/app/config", "/app/public"]

EXPOSE 80

CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
