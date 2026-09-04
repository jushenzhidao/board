# -*- coding: utf-8 -*-
"""
开发用桥接服务：把 ClickHouse HTTP 接口语义翻译到原生协议（9000 端口）。
启动后监听 127.0.0.1:8123，前端（vite proxy /ch -> 127.0.0.1:8123）即可直连查询。

同时提供多站点管理端点（站点配置存于 config/sites.json，凭据 write-only 不出站）：
    GET    /sites            -> 站点列表（id/name，不含凭据）
    GET    /sites/<id>       -> 单站点配置（密码脱敏为空）
    POST   /sites            -> 新建/更新站点（body: {"site": {...}}）
    DELETE /sites/<id>       -> 删除站点
    POST   /sites/test       -> 测试站点 CH/MySQL 连通性（body: {"site": {...}}）
    POST   /sites/<id>/sync  -> 同步该站点渠道映射（调 sync_channels.py）

用法:
    python scripts/dev_bridge.py
可选环境变量:
    BRIDGE_HOST (默认 127.0.0.1)  BRIDGE_PORT (默认 8123)
    BOARD_TOKEN (访问令牌；空 = 不启用认证)
    CH_HOST / CH_PORT / CH_USER / CH_PASSWORD / CH_DB
"""
import datetime
import hmac
import json
import math
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from clickhouse_driver import Client

# 限制同时向 ClickHouse 发起的查询连接数；CH 端/网络对突发连接敏感，
# 并发过大时部分连接会被排队 30s+。4 是经验值（>90% 查询 <1s）。
_CH_QUERY_SEM = threading.Semaphore(4)

CH_CONF_KEYS = ("host", "port", "user", "password", "database")

# 访问令牌：从环境变量 BOARD_TOKEN 读取。为空 = 不启用认证（本地开发向后兼容）。
# 启用后除 /ping 与 OPTIONS 外的所有请求须携带 Authorization: Bearer <token> 或 X-Board-Token: <token>。
BOARD_TOKEN = os.environ.get("BOARD_TOKEN", "").strip()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES_PATH = os.path.join(ROOT, "config", "sites.json")
PUBLIC_SITES_PATH = os.path.join(ROOT, "public", "sites.json")

_SITE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _load_from_file():
    """读 config/sites.json；文件缺失/解析失败/为空返回 None（不回退，用于热加载安全判断）。"""
    try:
        with open(SITES_PATH, encoding="utf-8") as f:
            sites = (json.load(f).get("sites")) or []
        return sites or None
    except Exception:
        return None


def _env_fallback_site():
    return [
        {
            "id": os.environ.get("BRIDGE_DEFAULT_SITE_ID", "default"),
            "name": "default",
            "ch": {
                "host": os.environ.get("CH_HOST", "103.207.68.201"),
                "port": int(os.environ.get("CH_PORT", "9000")),
                "user": os.environ.get("CH_USER", "default"),
                "password": os.environ.get("CH_PASSWORD", "ChangeMe_CH_Strong_Pwd_2026"),
                "database": os.environ.get("CH_DB", "new_api_logs"),
            },
        }
    ]


SITES = _load_from_file() or _env_fallback_site()
SITES_BY_ID = {s["id"]: s for s in SITES}
DEFAULT_SITE_ID = SITES[0]["id"]

_sites_lock = threading.Lock()
_sites_mtime = os.path.getmtime(SITES_PATH) if os.path.exists(SITES_PATH) else None


def reload_sites_if_changed():
    """热加载：sites.json 变更（mtime 变化且能正常解析）后自动生效，无需重启桥接。
    解析失败/为空时保留旧配置，避免坏配置把服务打挂。"""
    global SITES, SITES_BY_ID, DEFAULT_SITE_ID, _sites_mtime
    with _sites_lock:
        try:
            m = os.path.getmtime(SITES_PATH)
        except OSError:
            return
        if m == _sites_mtime:
            return
        sites = _load_from_file()
        if not sites:
            return  # 坏配置：保持现状
        SITES = sites
        SITES_BY_ID = {s["id"]: s for s in sites}
        DEFAULT_SITE_ID = sites[0]["id"]
        _sites_mtime = m
        print(f"[dev_bridge] sites.json reloaded: {len(sites)} 个站点（默认: {DEFAULT_SITE_ID}）")


def _write_sites(sites):
    """原子写回 sites.json 并同步内存态（调用方需已持有 _sites_lock）。"""
    global SITES, SITES_BY_ID, DEFAULT_SITE_ID, _sites_mtime
    os.makedirs(os.path.dirname(SITES_PATH), exist_ok=True)
    tmp = SITES_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"sites": sites}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SITES_PATH)
    SITES = sites
    SITES_BY_ID = {s["id"]: s for s in sites}
    DEFAULT_SITE_ID = sites[0]["id"] if sites else None
    try:
        _sites_mtime = os.path.getmtime(SITES_PATH)
    except OSError:
        _sites_mtime = None
    _refresh_sites_index(sites)


def _refresh_sites_index(sites):
    """同步 public/sites.json 索引（前端静态降级用，不含凭据）。"""
    try:
        os.makedirs(os.path.dirname(PUBLIC_SITES_PATH), exist_ok=True)
        with open(PUBLIC_SITES_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": datetime.datetime.now().isoformat(),
                    "sites": [{"id": s["id"], "name": s.get("name", s["id"])} for s in sites],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:
        print(f"[dev_bridge] 更新站点索引失败：{e}")


def _mask_secret(site):
    """站点配置脱敏副本：密码置空并加 has_password 标记（编辑回填时不留明文密码）。"""
    out = json.loads(json.dumps(site, ensure_ascii=False))
    for key in ("ch", "mysql"):
        block = out.get(key)
        if isinstance(block, dict):
            block["has_password"] = bool(block.get("password"))
            block["password"] = ""
    return out


def _merge_secrets(new_site, existing):
    """保存/测试时：密码字段为空且已有旧密码 -> 保留旧密码（write-only，不覆盖）。"""
    for key in ("ch", "mysql"):
        nb = new_site.get(key)
        if not isinstance(nb, dict):
            continue
        ob = (existing or {}).get(key) or {}
        if not nb.get("password") and ob.get("password"):
            nb["password"] = ob["password"]
        nb.pop("has_password", None)
    return new_site


def _validate_site(site):
    if not isinstance(site, dict):
        return "站点配置必须是 JSON 对象"
    sid = (site.get("id") or "").strip()
    if not sid:
        return "站点 ID 不能为空"
    if not _SITE_ID_RE.match(sid):
        return "站点 ID 只能含字母/数字/下划线/连字符（1-32 位）"
    if not (site.get("name") or "").strip():
        return "站点名称不能为空"
    ch = site.get("ch")
    if not isinstance(ch, dict) or not (ch.get("host") or "").strip():
        return "ClickHouse 地址（host）不能为空"
    try:
        int(ch.get("port") or 9000)
    except (TypeError, ValueError):
        return "ClickHouse 端口必须是数字"
    if not (ch.get("database") or "").strip():
        return "ClickHouse 数据库名不能为空"
    mysql = site.get("mysql")
    if mysql is not None and not isinstance(mysql, dict):
        return "MySQL 配置必须是对象"
    if isinstance(mysql, dict) and mysql.get("port") not in (None, ""):
        try:
            int(mysql.get("port"))
        except (TypeError, ValueError):
            return "MySQL 端口必须是数字"
    return None


def ch_conf_for(site_id):
    """站点 id -> 该站点 ClickHouse 连接配置；未知站点抛 ValueError。"""
    site = SITES_BY_ID.get(site_id)
    if not site:
        raise ValueError(f"unknown site '{site_id}'（可选：{', '.join(SITES_BY_ID)}）")
    conf = {"connect_timeout": 10, "send_receive_timeout": 30}
    conf.update({k: site["ch"][k] for k in CH_CONF_KEYS if k in site.get("ch", {})})
    return conf


def run_query(conf, sql):
    """执行查询；网络类瞬时错误（超时/连接中断）自动重试 1 次。
    使用信号量限制同时向 CH 发起的连接数，避免突发连接排队。"""
    last = None
    with _CH_QUERY_SEM:
        for attempt in (1, 2):
            try:
                cli = Client(**conf)
                return cli.execute(sql, with_column_types=True)
            except Exception as e:
                last = e
                transient = isinstance(
                    e, (TimeoutError, ConnectionError, ConnectionResetError, ConnectionAbortedError)
                )
                if attempt == 1 and transient:
                    continue  # 重试一次
                raise
    raise last


HAS_FMT = re.compile(r"FORMAT\s+[A-Za-z0-9_]+\s*;?\s*$", re.IGNORECASE)


def to_jsonable(v):
    if isinstance(v, datetime.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(v.tzinfo)
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (list, tuple)):  # CH Array/Tuple -> JSON 数组（与 CH FORMAT JSON 一致）
        return [to_jsonable(x) for x in v]
    if isinstance(v, (int, str, bool)) or v is None:
        return v
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else v
    try:  # Decimal 等
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except Exception:
        return str(v)


def _read_body(handler):
    length = int(handler.headers.get("Content-Length") or 0)
    return handler.rfile.read(length).decode("utf-8", "replace") if length else ""


def _parse_json_body(handler):
    raw = _read_body(handler)
    try:
        return json.loads(raw)
    except Exception:
        return None


def _test_ch(site):
    conf = {"connect_timeout": 8, "send_receive_timeout": 12}
    ch = site.get("ch") or {}
    for k in CH_CONF_KEYS:
        if k in ch:
            conf[k] = ch[k]
    Client(**conf).execute("SELECT 1")
    return None  # 无错误


def _test_mysql(site):
    mysql = site.get("mysql")
    if not isinstance(mysql, dict) or not mysql.get("host"):
        return None  # 无 mysql 配置，跳过
    try:
        import pymysql
    except ImportError:
        return "pymysql 未安装，无法测试 MySQL 连接"
    try:
        conn = pymysql.connect(
            host=mysql.get("host"),
            port=int(mysql.get("port") or 3306),
            user=mysql.get("user"),
            password=mysql.get("password") or "",
            database=mysql.get("database"),
            charset="utf8mb4",
            connect_timeout=8,
            read_timeout=12,
            write_timeout=12,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
    except Exception as e:
        return str(e)
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # 安静模式

    def _log_req(self, method, status=0, extra=""):
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        site = self.headers.get("X-Site") or "default"
        print(f"[{ts}] {method} {self.path} site={site} status={status}{extra}", flush=True)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def _authed(self):
        """校验访问令牌；未配置 BOARD_TOKEN 时放行（向后兼容）。恒时比较防时序攻击。"""
        if not BOARD_TOKEN:
            return True
        token = self.headers.get("X-Board-Token", "")
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        return bool(token) and hmac.compare_digest(token, BOARD_TOKEN)

    def _require_auth(self):
        if self._authed():
            return True
        self._send_json(401, {"error": "unauthorized"})
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        self._log_req("GET")
        if path == "/ping":
            body = b"Ok.\n"
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif not self._require_auth():
            return
        elif path == "/sites":
            reload_sites_if_changed()
            body = json.dumps(
                {"sites": [{"id": s["id"], "name": s.get("name", s["id"])} for s in SITES]}
            ).encode("utf-8")
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=UTF-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith("/sites/"):
            reload_sites_if_changed()
            site_id = unquote(path[len("/sites/"):])
            site = SITES_BY_ID.get(site_id)
            if not site:
                self._send_json(404, {"error": f"unknown site '{site_id}'"})
                return
            self._send_json(200, {"site": _mask_secret(site)})
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        reload_sites_if_changed()
        if not self._require_auth():
            return
        if path == "/sites":
            self._log_req("POST")
            self._handle_save_site()
            return
        if path == "/sites/test":
            self._log_req("POST")
            self._handle_test_site()
            return
        if path.startswith("/sites/") and path.endswith("/sync"):
            self._log_req("POST")
            self._handle_sync_site(unquote(path[len("/sites/"):-len("/sync")]))
            return
        # 其余 POST：ClickHouse SQL 查询
        raw = _read_body(self)
        query = None
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if "query" in qs:
            query = unquote(qs["query"][0])
        site_id = self.headers.get("X-Site") or qs.get("site", [""])[0]
        site_id = site_id or DEFAULT_SITE_ID
        sql_preview = (query or raw).strip().splitlines()[0][:60]
        self._log_req("POST", extra=f" site_id={site_id} sql={sql_preview!r}")
        try:
            ch_conf = ch_conf_for(site_id)
        except ValueError as e:
            self._log_req("POST", status=400)
            self._send_json(400, {"error": str(e)})
            return
        body_sql = (query or raw).strip().rstrip(";")
        if not body_sql:
            self._send_json(400, {"error": "empty query"})
            return
        if not HAS_FMT.search(body_sql):
            body_sql += " FORMAT JSON"
        t0 = datetime.datetime.now()
        try:
            rows, cols = run_query(ch_conf, body_sql)
        except Exception as e:
            self._log_req("POST", status=500, extra=f" elapsed={(datetime.datetime.now()-t0).total_seconds():.2f}s")
            self._send_json(500, {"error": str(e)})
            return
        elapsed = (datetime.datetime.now() - t0).total_seconds()
        names = [c[0] for c in cols]
        types = [c[1] for c in cols]
        data = [dict(zip(names, [to_jsonable(v) for v in row])) for row in rows]
        meta = [{"name": n, "type": t} for n, t in zip(names, types)]
        self._log_req("POST", status=200, extra=f" elapsed={elapsed:.2f}s rows={len(rows)}")
        self._send_json(200, {
            "meta": meta,
            "data": data,
            "rows": len(data),
            "rows_read": len(rows),
            "statistics": {"elapsed": elapsed},
        })

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not self._require_auth():
            return
        if path.startswith("/sites/"):
            self._handle_delete_site(unquote(path[len("/sites/"):]))
        else:
            self.send_error(404)

    # ---------- 站点管理 ----------

    def _handle_save_site(self):
        payload = _parse_json_body(self)
        site = payload.get("site") if isinstance(payload, dict) else None
        err = _validate_site(site)
        if err:
            self._send_json(400, {"error": err})
            return
        with _sites_lock:
            existing = SITES_BY_ID.get(site["id"])
            site = _merge_secrets(site, existing)
            sites = list(SITES)
            if existing:
                for i, s in enumerate(sites):
                    if s["id"] == site["id"]:
                        sites[i] = site
                        break
            else:
                sites.append(site)
            _write_sites(sites)
        print(f"[dev_bridge] 站点已{'更新' if existing else '新增'}：{site['id']} ({site.get('name')})")
        self._send_json(200, {"ok": True, "site": {"id": site["id"], "name": site.get("name", site["id"])}})

    def _handle_delete_site(self, site_id):
        with _sites_lock:
            if site_id not in SITES_BY_ID:
                self._send_json(404, {"error": f"unknown site '{site_id}'"})
                return
            sites = [s for s in SITES if s["id"] != site_id]
            _write_sites(sites)
        # 顺手清理该站点的渠道映射文件（残留无害，但保持 public/channels/ 干净）
        if _SITE_ID_RE.match(site_id):
            ch_file = os.path.join(ROOT, "public", "channels", f"{site_id}.json")
            try:
                if os.path.exists(ch_file):
                    os.remove(ch_file)
                    print(f"[dev_bridge] 已清理渠道映射文件：{ch_file}")
            except OSError as e:
                print(f"[dev_bridge] 清理渠道映射文件失败：{e}")
        print(f"[dev_bridge] 站点已删除：{site_id}（剩余 {len(sites)} 个）")
        self._send_json(200, {"ok": True})

    def _handle_test_site(self):
        payload = _parse_json_body(self)
        site = payload.get("site") if isinstance(payload, dict) else None
        if not isinstance(site, dict):
            self._send_json(400, {"error": "请求体缺少 site 对象"})
            return
        with _sites_lock:
            existing = SITES_BY_ID.get(site.get("id"))
            if existing:
                site = _merge_secrets(dict(site), existing)
        ch_err = _test_ch(site)
        mysql_skipped = not isinstance(site.get("mysql"), dict) or not site["mysql"].get("host")
        mysql_err = None if mysql_skipped else _test_mysql(site)
        self._send_json(200, {
            "ok": True,
            "ch": {"ok": ch_err is None, "error": ch_err},
            "mysql": {"ok": mysql_err is None, "error": mysql_err, "skipped": mysql_skipped},
        })

    def _handle_sync_site(self, site_id):
        site = SITES_BY_ID.get(site_id)
        if not site:
            self._send_json(404, {"error": f"unknown site '{site_id}'"})
            return
        try:
            import sync_channels  # noqa: F401  同目录模块
        except ImportError as e:
            self._send_json(500, {"error": f"无法加载渠道同步模块：{e}"})
            return
        try:
            n = sync_channels.sync_site(site)
        except Exception as e:
            self._send_json(500, {"error": f"渠道同步失败：{e}"})
            return
        self._send_json(200, {"ok": True, "channels": n})

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=UTF-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    host = os.environ.get("BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("BRIDGE_PORT", "8123"))
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"[dev_bridge] listening on http://{host}:{port}  ->  {len(SITES)} 个站点（默认: {DEFAULT_SITE_ID}）")
    print(f"[dev_bridge] 访问令牌认证：{'已启用（BOARD_TOKEN）' if BOARD_TOKEN else '未启用（未设置 BOARD_TOKEN，向后兼容）'}")
    for s in SITES:
        print(f"  - {s['id']}: {s['ch'].get('host')}:{s['ch'].get('port')}/{s['ch'].get('database')}")
    print("[dev_bridge] 站点管理端点：GET/POST/DELETE /sites、POST /sites/test、POST /sites/<id>/sync")
    print("[dev_bridge] 前端 /ch 代理已指向本服务（vite.config.js），请求头 X-Site 指定站点")
    srv.serve_forever()


if __name__ == "__main__":
    main()
