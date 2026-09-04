# -*- coding: utf-8 -*-
"""渠道看板 - MySQL 渠道映射 + CH 补充验证"""
import pymysql
from clickhouse_driver import Client

cli = Client(host="103.207.68.201", port=9000, user="default",
             password="ChangeMe_CH_Strong_Pwd_2026", database="new_api_logs",
             connect_timeout=10, send_receive_timeout=60)

def sec(t):
    print("\n" + "=" * 60)
    print("## " + t)
    print("=" * 60)

# --- CH 补充验证 ---
sec("A. type=5 错误日志（用 channel_id，group 加反引号）")
for r in cli.execute("""
    SELECT request_id, JSONExtractString(other, 'error_type'),
           JSONExtractUInt(other, 'status_code'), channel_id, model_name, username,
           substr(content, 1, 80), created_at
    FROM logs WHERE type = 5 ORDER BY created_at DESC LIMIT 5
"""):
    print(" ", r)

sec("B. 维度基数（channel_id 版）")
print(cli.execute("""
    SELECT uniqExact(channel_id) AS channels, uniqExact(model_name) AS models,
           uniqExact(username) AS users, uniqExact(token_name) AS tokens,
           uniqExact(`group`) AS groups,
           uniqExact((channel_id, JSONExtractInt(other, 'admin_info', 'multi_key_index'))) AS ch_keys
    FROM logs WHERE type = 2
"""))

sec("C. use_time>=frt/1000 判定（秒口径复核）")
print(cli.execute("""
    SELECT countIf(use_time * 1000 >= frt) AS ge, countIf(use_time * 1000 < frt) AS lt
    FROM (SELECT use_time, JSONExtractUInt(other, 'frt') AS frt FROM logs
          WHERE type = 2 AND is_stream = 1 AND JSONExtractUInt(other, 'frt') > 0)
"""))

sec("D. CH logs 里出现的 channel_id 清单")
print(cli.execute("SELECT DISTINCT channel_id FROM logs ORDER BY channel_id"))

# --- MySQL ---
sec("M1. MySQL 连接 / 库表清单")
my = pymysql.connect(host="103.207.68.201", port=3306, user="root",
                     password="cbe1449JtNx7hMm8", database="oneapi-master",
                     connect_timeout=10, charset="utf8mb4")
cur = my.cursor()
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print(" ", tables)

if "channels" in tables:
    sec("M2. channels 表结构")
    cur.execute("DESCRIBE channels")
    cols = [r[0] for r in cur.fetchall()]
    print(" ", cols)

    sec("M3. channels 数据（id/name/type/status）")
    cur.execute("SELECT id, name, type, status FROM channels ORDER BY id")
    for r in cur.fetchall():
        print(" ", r)

if "tokens" in tables:
    sec("M4. tokens 表（字段确认）")
    cur.execute("DESCRIBE tokens")
    print(" ", [r[0] for r in cur.fetchall()])

if "users" in tables:
    sec("M5. users 表（字段确认）")
    cur.execute("DESCRIBE users")
    print(" ", [r[0] for r in cur.fetchall()])

my.close()
print("\nDONE")
