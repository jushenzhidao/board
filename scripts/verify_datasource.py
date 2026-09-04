# -*- coding: utf-8 -*-
"""渠道看板 - 数据源验证脚本 v2（每段独立 try/except）"""
from clickhouse_driver import Client

cli = Client(host="103.207.68.201", port=9000, user="default",
             password="ChangeMe_CH_Strong_Pwd_2026", database="new_api_logs",
             connect_timeout=10, send_receive_timeout=60)

def sec(title):
    print("\n" + "=" * 60)
    print("## " + title)
    print("=" * 60)

def run(title, sql):
    sec(title)
    try:
        for r in cli.execute(sql):
            print(" ", r)
    except Exception as e:
        print("  ERROR:", str(e).split("\n")[0][:300])

# 3. 数据量与时间范围（created_at 为 Int64 时间戳）
run("3. 数据量 / 时间范围 / 每日量", """
    SELECT count(), min(created_at), max(created_at) FROM logs
""")
run("3b. 时间戳单位判定（若 max ~ 1.78e9 为秒，~ 1.78e12 为毫秒）", """
    SELECT max(created_at) / 1e9, max(created_at) / 1e12 FROM logs
""")
run("3c. 每日量（按秒假设）", """
    SELECT toDate(toDateTime(created_at)) d, count() c
    FROM logs GROUP BY d ORDER BY d DESC LIMIT 7
""")

# 4. type 分布
run("4. type 分布", "SELECT type, count() FROM logs GROUP BY type ORDER BY type")

# 5. use_time 单位判定
run("5. use_time vs frt（流式成功请求）", """
    SELECT use_time, JSONExtractUInt(other, 'frt') AS frt, model_name, prompt_tokens, completion_tokens
    FROM logs WHERE type = 2 AND is_stream = 1 AND JSONExtractUInt(other, 'frt') > 0
    ORDER BY created_at DESC LIMIT 8
""")
run("5b. 比例判定（ge=use_time>=frt → 同为毫秒；lt=use_time<frt → use_time 为秒）", """
    SELECT countIf(use_time >= frt) AS ge_frt, countIf(use_time < frt) AS lt_frt
    FROM logs
    WHERE type = 2 AND is_stream = 1 AND JSONExtractUInt(other, 'frt') > 0
      AND created_at >= (toUnixTimestamp(now()) - 7 * 86400)
""")

# 6. type=5 错误日志样本
run("6a. type=5 错误日志字段样本", """
    SELECT request_id, JSONExtractString(other, 'error_type'),
           JSONExtractUInt(other, 'status_code'), channel_name, channel_id, model_name, username,
           substr(content, 1, 100), created_at
    FROM logs WHERE type = 5 ORDER BY created_at DESC LIMIT 3
""")
run("6b. type=5 other 完整样本", """
    SELECT other FROM logs WHERE type = 5 ORDER BY created_at DESC LIMIT 1
""")
run("6c. type=5 request_id 空值率", """
    SELECT count(), countIf(request_id = '') FROM logs WHERE type = 5
""")

# 7. request_id 归并验证
run("7. request_id 归并（最终结果口径）", """
    WITH success_ids AS (
        SELECT DISTINCT request_id FROM logs WHERE type = 2 AND request_id != ''
          AND created_at >= (toUnixTimestamp(now()) - 7 * 86400)
    )
    SELECT
      (SELECT count() FROM success_ids) AS total_success,
      count() AS total_err_rows,
      countIf(request_id NOT IN success_ids) AS final_fail_req
    FROM logs
    WHERE type = 5 AND request_id != ''
      AND created_at >= (toUnixTimestamp(now()) - 7 * 86400)
""")

# 8. 维度基数
run("8. 维度基数（渠道/模型/用户/令牌/分组/Key）", """
    SELECT
      uniqExact(channel_name) AS channels,
      uniqExact(model_name) AS models,
      uniqExact(username) AS users,
      uniqExact(token_name) AS tokens,
      uniqExact(group) AS groups,
      uniqExact((channel_name, JSONExtractInt(other, 'admin_info', 'multi_key_index'))) AS channel_keys
    FROM logs WHERE type = 2
""")

# 9. other 关键字段覆盖率
run("9. other 字段覆盖率（近7天成功请求）", """
    SELECT count() AS total,
      countIf(JSONExtractUInt(other, 'frt') > 0) AS has_frt,
      countIf(JSONExtractUInt(other, 'cache_tokens') > 0) AS has_cache,
      countIf(length(JSONExtractArrayRaw(other, 'admin_info', 'use_channel')) > 1) AS has_retry,
      countIf(JSONHas(other, 'admin_info')) AS has_admin_info
    FROM logs
    WHERE type = 2 AND created_at >= (toUnixTimestamp(now()) - 7 * 86400)
""")

print("\nDONE")
