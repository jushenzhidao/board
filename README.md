# 渠道看板

new-api 网关渠道监控仪表盘（Vue3 + ECharts 前端应用，数据源为 ClickHouse 中的 new-api 日志库 `new_api_logs.logs`）。

## 指标口径（重要）

**"最终结果"口径（重试排除）**：按 `request_id` 归并——存在 type=2（消费）记录即最终成功；仅 type=5（报错）即最终失败。中间失败的尝试不进任何统计。

| 指标 | 定义 |
|------|------|
| 成功率 | 最终成功请求数 ÷ 总请求数 |
| FRT | 首字延迟（other.frt，毫秒），仅统计有 FRT 记录的请求；P50/P95/P99 |
| TPS | Σ输出token ÷ Σ生成时长（生成时长 = use_time×1000 − FRT，非流式 = use_time×1000），加权平均 |
| 平均耗时 | use_time（秒）均值 |
| 缓存命中率 | Σcache_tokens ÷ Σ输入token |
| 报错 | 最终失败请求；按 error_type / status_code 分布 |
| 重试数 | other.admin_info.use_channel 数组长度 > 1 的请求数 |

- 请求归属渠道：成功 → 最终成功方 channel_id；失败 → 最后一次尝试的 channel_id
- use_time 为秒级精度（new-api 原生），TPS 计算在秒边界可能有小误差
- 渠道名称来自 MySQL channels 表（`scripts/sync_channels.py` 按站点生成 `public/channels/<site>.json`），渠道变更后重新执行

## 多站点配置

站点（各自的 ClickHouse + MySQL）存于 **`config/sites.json`**（已 gitignore，不入库）：

```json
{
  "sites": [
    {
      "id": "main",
      "name": "主站",
      "ch":     { "host": "...", "port": 9000, "user": "...", "password": "...", "database": "new_api_logs" },
      "mysql":  { "host": "...", "port": 3306, "user": "...", "password": "...", "database": "oneapi-master" }
    },
    { "id": "site2", "name": "站点二", "ch": { "...": "..." }, "mysql": { "...": "..." } }
  ]
}
```

### 可视化管理（推荐）

前端顶栏「站点切换器」下拉底部有 **＋ 新增站点**，点击弹出配置弹窗（可保存/测试连接），已有站点可编辑（✎）或删除（🗑）。

- 站点配置的增删改由桥接服务 `/sites` 端点完成，**自动写回 `config/sites.json` 并热生效**，无需重启
- **密码 write-only**：浏览器永不回显明文密码——读取时密码脱敏为空，编辑时留空即保留原密码
- 保存站点后自动触发该站点的渠道同步（`POST /sites/<id>/sync`），渠道名即时可用

### 手动配置

直接编辑 `config/sites.json`，然后同步渠道映射：

```bash
python scripts/sync_channels.py        # 遍历全部站点生成 channels/<id>.json + sites.json 索引
python scripts/sync_channels.py --site site2   # 只同步某个站点
```

### 站点管理端点（dev_bridge.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sites` | 站点列表（id/name，不含凭据） |
| GET | `/sites/<id>` | 单站点配置（密码脱敏为空） |
| POST | `/sites` | 新建/更新站点（空密码 = 保留旧密码） |
| DELETE | `/sites/<id>` | 删除站点 |
| POST | `/sites/test` | 测试 CH/MySQL 连通性 |
| POST | `/sites/<id>/sync` | 同步该站点渠道映射 |

- 桥接服务按请求头 `X-Site` 路由到对应站点的 CH，**无需重启**（凭据只在服务端，浏览器不接触）
- 前端站点列表优先从 `/sites` 实时读取，失败回退 `public/sites.json`；当前站点记在 localStorage，切换即重置筛选并重载
- 未带 `X-Site` 头的请求默认路由到第一个站点（向后兼容）
- `dev_bridge.py` 缺少 config/sites.json 时回退到环境变量单站点（CH_HOST 等旧变量仍有效）

## 访问令牌认证

桥接服务可选启用访问令牌保护（内网多用户共用时建议开启）。设置环境变量 `BOARD_TOKEN` 即启用：

```bash
# 启用认证（令牌 = 环境变量值）
BOARD_TOKEN=your-secret-token python scripts/dev_bridge.py

# 不设置 = 不启用认证（本地开发向后兼容）
python scripts/dev_bridge.py
```

- 启用后，除 `/ping` 与 CORS 预检（OPTIONS）外的所有接口须携带令牌：`Authorization: Bearer <token>` 或 `X-Board-Token: <token>`
- 前端收到 401 自动弹出「访问令牌」登录框，令牌保存在浏览器 localStorage（`chBoard.settings` 的 `token` 字段），随请求头发出
- 令牌用 `hmac.compare_digest` 恒时比较，防时序攻击

## 本地开发

```bash
# 1. 启动桥接服务（HTTP -> ClickHouse 原生 9000；8123 未对外时必需）
python scripts/dev_bridge.py

# 2. 启动前端（vite 会把 /ch/ 代理到 127.0.0.1:8123）
npm install
npm run dev          # http://localhost:5173
```

## Docker 部署（推荐）

单镜像打包 nginx（静态 + 反代）与桥接服务，一条命令拉起；多站点/多环境可用 compose 管理。镜像不含任何站点凭据（`.dockerignore` 已排除）。

### 1. 首次准备站点配置

```bash
cp config/sites.example.json config/sites.json
# 编辑 config/sites.json，填入真实 ClickHouse / MySQL 地址与凭据
```

### 2. 构建镜像

```bash
docker build -t channel-board:latest .
```

### 3. 启动（docker compose）

```bash
# 可选：启用访问令牌（写进 .env，不入库）
# echo 'BOARD_TOKEN=你的令牌' > .env

docker compose up -d --build
```

访问 `http://<宿主机IP>:8080`（端口见 `docker-compose.yml` 的 `ports`）。

### 4. 或纯 docker run（不用 compose）

```bash
docker run -d --name channel-board \
  -p 8080:80 \
  -e TZ=Asia/Shanghai \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/public:/app/public" \
  --restart unless-stopped \
  channel-board:latest
```

需启用访问令牌时追加 `-e BOARD_TOKEN=你的令牌`。

### 5. GitHub Actions 自动构建镜像（可选）

推送到 GitHub 后，`.github/workflows/build-image.yml` 会在 **push 到 main/master、打 `v*` 标签、或手动触发** 时自动构建镜像并推送到 **GHCR**（`ghcr.io/<owner>/channel-board`，用内置 `GITHUB_TOKEN`，无需额外密钥）。

| 触发 | 镜像标签 |
|------|---------|
| push 到默认分支 | `latest`、`main`、`<commit-sha>` |
| push `v*` 标签 | `v1.2.3`、`v1.2`、`1.2.3`、`<commit-sha>` |
| 手动 workflow_dispatch | 同上（按当前 ref） |

服务器拉取：

```bash
# 私有镜像先登录 GHCR（用 Personal Access Token）
echo $GITHUB_PAT | docker login ghcr.io -u <你的用户名> --password-stdin
docker pull ghcr.io/<owner>/channel-board:latest
```

> 如需推送到 Docker Hub，取消 workflow 中对应注释并配置 `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` 两个仓库 secrets。

### 镜像内架构

| 组件 | 端口 | 说明 |
|------|------|------|
| nginx | 80 | 托管 `dist/` 静态 + `/sites.json`、`/channels/*`（挂载卷）+ `/ch/` 反代桥接 |
| dev_bridge.py | 8123（容器内） | ClickHouse HTTP 语义 → 原生 9000；按 `X-Site` 路由多站点；站点管理端点 |
| supervisor | — | 守护 nginx 与桥接，异常自动重启 |

- 站点凭据只存在于宿主机 `./config/sites.json`（挂载卷），**不进镜像层**
- 渠道映射/站点索引写到挂载卷 `./public`，容器重建不丢
- 改 `config/sites.json` 后桥接自动热加载，无需重启容器
- 内网部署可关掉 `ports` 映射，改用宿主机 nginx 反代到容器（`expose 80`）

## 手动部署（内网 nginx，不用 Docker）

```bash
npm run build                    # 产出 dist/（含 public/channels/ 与 sites.json）
python scripts/sync_channels.py  # 刷新各站点渠道映射
```

nginx 配置见 `nginx/board.conf`：静态托管 `dist/` + `/ch/` 反代 ClickHouse HTTP（8123）。
CH 的 8123 无需对公网开放，nginx 同机走 127.0.0.1。建议创建只读账号 `board_ro`（GRANT SELECT ON new_api_logs.*）并在 nginx 侧注入认证。

**多站点生产部署**：直连 CH 8123 无法按 X-Site 路由，两种方式任选：
1. 生产也跑 `dev_bridge.py`（`BRIDGE_HOST=127.0.0.1`），nginx `/ch/` 反代到桥接而非 CH 直连——请求头透传即可按站点路由
2. 每个站点一个 nginx location（`/ch-main/`、`/ch-site2/`），各自反代对应站点的 CH

## 目录结构

```
├── index.html
├── Dockerfile                # 单镜像多阶段构建（node 构建前端 → python+nginx 运行时）
├── docker-compose.yml        # 编排：挂载 config/public 卷、注入 BOARD_TOKEN
├── .dockerignore             # 构建上下文排除（凭据/产物/记忆不入镜像）
├── .github/workflows/build-image.yml  # GitHub Actions：自动构建并推送镜像到 GHCR
├── requirements.txt          # 桥接 Python 依赖（clickhouse-driver / pymysql）
├── docker/
│   ├── nginx.conf            # 容器内 nginx：静态 + /ch/ 反代 + sites.json/channels
│   └── supervisord.conf      # 守护 nginx + dev_bridge.py
├── config/sites.json         # 多站点映射（CH+MySQL 凭据，gitignore；模板见 sites.example.json）
├── public/sites.json         # 站点索引（不含凭据，sync_channels.py 生成）
├── public/channels/<id>.json # 各站点渠道 id->name 映射（sync_channels.py 生成）
├── src/
│   ├── App.vue                # 页面编排、筛选状态、数据加载、下钻、站点管理编排
│   ├── api/ch.js              # ClickHouse HTTP 查询客户端（连接设置存 localStorage）
│   ├── api/sites.js           # 站点管理 API 客户端（/sites CRUD + 测试 + 同步）
│   ├── api/sql.js             # 全部指标 SQL 构造器（核心）
│   ├── api/format.js          # 展示格式化
│   └── components/
│       ├── SiteSwitcher.vue   # 站点下拉（切换 + 新增/编辑/删除入口）
│       ├── SiteForm.vue       # 站点配置弹窗（CH/MySQL 表单 + 测试连接）
│       ├── LoginDialog.vue    # 访问令牌登录框（401 时弹出）
│       └── ...                # FilterBar/KpiCards/TrendCharts/DimTable/ErrorPanel/HeatMap/EChart/FSelect
├── scripts/
│   ├── dev_bridge.py          # 开发桥接：CH HTTP 语义 -> 原生 9000；站点管理端点
│   ├── sync_channels.py       # MySQL -> channels.json
│   ├── verify_datasource.py   # 数据源验证
│   ├── test_sql.py            # 指标 SQL 验证
│   ├── validate_queries.mjs   # 全量前端 SQL 构造器链路验证（16 查询 + 数组类型断言）
│   └── ssr_smoke.js           # SSR 冒烟测试（全组件渲染路径）
└── nginx/board.conf           # 生产部署配置示例
```

## 开发验证流程（每次改动后）

```bash
node scripts/validate_queries.mjs   # 全量 SQL 链路 + options/keyOptions 数组类型断言
node scripts/ssr_smoke.js           # 全组件 SSR 渲染冒烟（20 关键词）
```

## 已知边界

- 时间边界处的重试请求（失败在区间外、成功在区间内等）按区间内行归并，极端情况可能±1
- FRT 仅流式请求有值（new-api 行为），非流式请求不计入 FRT 分位数
- Key 维度依赖 other.admin_info.multi_key_index（多 Key 渠道）
