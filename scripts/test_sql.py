# -*- coding: utf-8 -*-
"""渠道看板 - 核心指标 SQL 验证（与前端将使用的 SQL 完全一致）"""
import json
from clickhouse_driver import Client

cli = Client(host="103.207.68.201", port=9000, user="default",
             password="ChangeMe_CH_Strong_Pwd_2026", database="new_api_logs",
             connect_timeout=10, send_receive_timeout=60)

REQS_CTE = """
WITH reqs AS (
  SELECT
    request_id,
    max(type = 2) = 1 AS ok,
    max(created_at) AS ts,
    argMax(channel_id, (type = 2, created_at)) AS channel_id,
    argMax(model_name, (type = 2, created_at)) AS model_name,
    argMax(username, (type = 2, created_at)) AS username,
    argMax(token_name, (type = 2, created_at)) AS token_name,
    argMax(`group`, (type = 2, created_at)) AS `group`,
    argMaxIf(use_time, created_at, type = 2) AS use_time_s,
    argMaxIf(JSONExtractUInt(other, 'frt'), created_at, type = 2) AS frt_ms,
    argMaxIf(prompt_tokens, created_at, type = 2) AS prompt_tokens,
    argMaxIf(completion_tokens, created_at, type = 2) AS completion_tokens,
    argMaxIf(JSONExtractUInt(other, 'cache_tokens'), created_at, type = 2) AS cache_tokens,
    argMaxIf(is_stream, created_at, type = 2) AS is_stream,
    argMaxIf(JSONExtractInt(other, 'admin_info', 'multi_key_index'), created_at, type = 2) AS key_idx,
    argMaxIf(JSONHas(other, 'admin_info', 'multi_key_index'), created_at, type = 2) AS is_multi_key,
    argMaxIf(length(JSONExtractArrayRaw(other, 'admin_info', 'use_channel')), created_at, type = 2) AS try_cnt,
    argMaxIf(JSONExtractString(other, 'error_type'), created_at, type = 5) AS error_type,
    argMaxIf(JSONExtractUInt(other, 'status_code'), created_at, type = 5) AS status_code,
    argMaxIf(substr(content, 1, 200), created_at, type = 5) AS error_msg
  FROM logs
  WHERE type IN (2, 5) AND request_id != ''
    AND created_at >= 1787226490 AND created_at < 1788425879
  GROUP BY request_id
)
"""

GEN_MS = "if(frt_ms > 0 AND use_time_s * 1000 > frt_ms, use_time_s * 1000 - frt_ms, if(frt_ms = 0, use_time_s * 1000, 0))"

def run(title, sql):
    print("\n" + "=" * 60)
    print("## " + title)
    print("=" * 60)
    try:
        _, cols = cli.execute("SELECT 1", with_column_types=True)  # warm
        res = cli.execute(sql, with_column_types=True)
        rows, types = res
        print("  cols:", [c[0] for c in types])
        for r in rows[:10]:
            print(" ", r)
        print("  rows:", len(rows))
    except Exception as e:
        print("  ERROR:", str(e)[:500])

# 1. KPI 总览
run("1. KPI 总览", f"""
{REQS_CTE}
SELECT
  count() AS total,
  countIf(ok) AS ok_cnt,
  round(countIf(ok) / count() * 100, 2) AS success_rate,
  quantileIf(0.5)(frt_ms, ok AND frt_ms > 0) AS frt_p50,
  quantileIf(0.95)(frt_ms, ok AND frt_ms > 0) AS frt_p95,
  round(sumIf(completion_tokens, ok AND {GEN_MS} > 0) /
        (sumIf({GEN_MS}, ok AND {GEN_MS} > 0) / 1000), 1) AS tps,
  round(avgIf(use_time_s, ok), 2) AS avg_use_time,
  round(sumIf(cache_tokens, ok) / nullIf(sumIf(prompt_tokens, ok), 0) * 100, 2) AS cache_rate,
  countIf(NOT ok) AS err_cnt,
  countIf(try_cnt > 1) AS retried_cnt
FROM reqs
""")

# 2. 维度表（按渠道）
run("2. 渠道维度表", f"""
{REQS_CTE}
SELECT
  channel_id,
  count() AS total,
  countIf(ok) AS ok_cnt,
  round(countIf(ok) / count() * 100, 2) AS success_rate,
  quantileIf(0.5)(frt_ms, ok AND frt_ms > 0) AS frt_p50,
  quantileIf(0.95)(frt_ms, ok AND frt_ms > 0) AS frt_p95,
  round(sumIf(completion_tokens, ok AND {GEN_MS} > 0) /
        (sumIf({GEN_MS}, ok AND {GEN_MS} > 0) / 1000), 1) AS tps,
  round(avgIf(use_time_s, ok), 2) AS avg_use_time,
  round(sumIf(cache_tokens, ok) / nullIf(sumIf(prompt_tokens, ok), 0) * 100, 2) AS cache_rate,
  countIf(NOT ok) AS err_cnt,
  countIf(try_cnt > 1) AS retried_cnt
FROM reqs
GROUP BY channel_id ORDER BY total DESC
""")

# 3. 时间趋势（按天）
run("3. 时间趋势（按天）", f"""
{REQS_CTE}
SELECT
  toStartOfDay(toDateTime(ts, 'Asia/Shanghai'), 'Asia/Shanghai') AS t,
  count() AS total,
  countIf(ok) AS ok_cnt,
  countIf(NOT ok) AS err_cnt,
  quantileIf(0.5)(frt_ms, ok AND frt_ms > 0) AS frt_p50,
  sumIf(completion_tokens, ok) AS out_toks
FROM reqs
GROUP BY t ORDER BY t
""")

# 4. 报错分布
run("4. 报错分布", f"""
{REQS_CTE}
SELECT error_type, status_code, count() AS cnt
FROM reqs WHERE NOT ok
GROUP BY error_type, status_code ORDER BY cnt DESC
""")

# 5. 报错明细
run("5. 报错明细", f"""
{REQS_CTE}
SELECT ts, channel_id, model_name, username, error_type, status_code, error_msg, request_id
FROM reqs WHERE NOT ok
ORDER BY ts DESC LIMIT 5
""")

# 6. 维度选项（筛选项下拉）
run("6. 维度选项", """
SELECT
  groupUniqArray(10000)(channel_id),
  groupUniqArray(10000)(model_name),
  groupUniqArray(10000)(username),
  groupUniqArray(10000)(token_name),
  groupUniqArray(10000)(`group`)
FROM logs WHERE type IN (2, 5)
""")

print("\nSQL-ALL-DONE")
