# -*- coding: utf-8 -*-
"""
从 new-api 主库（MySQL）同步渠道 id -> name 映射到 public/channels/<site>.json，
并生成站点索引 public/sites.json。多站点配置见 config/sites.json。

用法:
    python scripts/sync_channels.py            # 同步全部站点
    python scripts/sync_channels.py --site main # 只同步指定站点
"""
import json
import os
import sys
from datetime import datetime

import pymysql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES_PATH = os.path.join(ROOT, "config", "sites.json")
OUT_DIR = os.path.join(ROOT, "public", "channels")


def load_sites():
    with open(SITES_PATH, encoding="utf-8") as f:
        return (json.load(f).get("sites")) or []


def sync_site(site):
    mysql = site["mysql"]
    conn = pymysql.connect(
        host=mysql.get("host"), port=int(mysql.get("port", 3306)),
        user=mysql.get("user"), password=mysql.get("password"),
        database=mysql.get("database"), charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, type, status FROM channels ORDER BY id")
            rows = [{"id": r[0], "name": r[1], "type": r[2], "status": r[3]} for r in cur.fetchall()]
    finally:
        conn.close()

    out = os.path.join(OUT_DIR, f"{site['id']}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"site": site["id"], "generated_at": datetime.now().isoformat(), "channels": rows},
                  f, ensure_ascii=False, indent=2)
    print(f"[sync_channels] {site['id']}: {len(rows)} channels -> {out}")
    for c in rows:
        print(f"  {c['id']:>3}  {c['name']}")
    return len(rows)


def main():
    only = None
    if "--site" in sys.argv:
        only = sys.argv[sys.argv.index("--site") + 1]
    sites = [s for s in load_sites() if not only or s["id"] == only]
    if not sites:
        print("config/sites.json 中没有匹配的站点")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    for site in sites:
        try:
            sync_site(site)
        except Exception as e:
            print(f"[sync_channels] {site['id']}: FAILED - {e}")

    # 站点索引（不含任何凭据，前端用于站点切换器）
    with open(os.path.join(ROOT, "public", "sites.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(),
                   "sites": [{"id": s["id"], "name": s.get("name", s["id"])} for s in sites]},
                  f, ensure_ascii=False, indent=2)
    print("[sync_channels] 站点索引 -> public/sites.json")


if __name__ == "__main__":
    main()
