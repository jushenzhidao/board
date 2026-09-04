// 指标 SQL 构造器
// 口径约定（"最终结果"）:
//  - 按 request_id 归并：存在 type=2 记录 = 最终成功；仅 type=5 = 最终失败
//  - 请求归属渠道：成功 -> type=2 行的 channel_id（最终成功方）；
//    失败 -> 最后一次尝试的 channel_id
//  - 中间失败的尝试（重试产生）不进任何统计

// 生成时长（毫秒）：流式 = use_time*1000 - frt；非流式 = use_time*1000；异常 = 0（剔除）
const GEN_MS =
  "if(frt_ms > 0 AND use_time_s * 1000 > frt_ms, use_time_s * 1000 - frt_ms, if(frt_ms = 0, use_time_s * 1000, 0))"

const q = (s) => "'" + String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'"

// 非数字安全包装：无样本时输出 null（避免 CH 输出 NaN 破坏 JSON）
const safe = (expr, guard) => `if((${guard}) = 0, null, ${expr})`

/**
 * 构建 request 级 CTE。f: { t0, t1, users, models, tokens, groups }
 * 渠道/Key 过滤在归并之后（外层）做，保证"最终归属"语义。
 */
export function buildReqs(f) {
  const pre = []
  if (f.users?.length) pre.push(`username IN (${f.users.map(q).join(',')})`)
  if (f.models?.length) pre.push(`model_name IN (${f.models.map(q).join(',')})`)
  if (f.tokens?.length) pre.push(`token_name IN (${f.tokens.map(q).join(',')})`)
  if (f.groups?.length) pre.push('`group` IN (' + f.groups.map(q).join(',') + ')')

  // 注意：行级过滤必须在子查询 src 里做。若直接放在聚合 SELECT 的 WHERE，
  // argMax(...) AS model_name 等别名会遮蔽源列，WHERE 里 model_name 被展开成
  // 聚合表达式，报 "Aggregate function ... is found in WHERE"（CH 别名遮蔽陷阱）。
  return `WITH src AS (
  SELECT *
  FROM new_api_logs.logs
  WHERE type IN (2, 5) AND request_id != ''
    AND created_at >= ${Math.floor(f.t0)} AND created_at < ${Math.floor(f.t1)}
    ${pre.length ? 'AND ' + pre.join('\n    AND ') : ''}
), reqs AS (
  SELECT
    request_id,
    max(type = 2) = 1 AS ok,
    max(created_at) AS ts,
    argMax(channel_id, (type = 2, created_at)) AS channel_id,
    argMax(model_name, (type = 2, created_at)) AS model_name,
    argMax(username, (type = 2, created_at)) AS username,
    argMax(token_name, (type = 2, created_at)) AS token_name,
    argMax(\`group\`, (type = 2, created_at)) AS \`group\`,
    argMaxIf(use_time, created_at, type = 2) AS use_time_s,
    argMaxIf(JSONExtractUInt(other, 'frt'), created_at, type = 2) AS frt_ms,
    argMaxIf(prompt_tokens, created_at, type = 2) AS prompt_tokens,
    argMaxIf(completion_tokens, created_at, type = 2) AS completion_tokens,
    argMaxIf(JSONExtractUInt(other, 'cache_tokens'), created_at, type = 2) AS cache_tokens,
    argMaxIf(is_stream, created_at, type = 2) AS is_stream,
    argMaxIf(JSONExtractInt(other, 'admin_info', 'multi_key_index'), created_at, type = 2) AS key_idx,
    argMaxIf(length(JSONExtractArrayRaw(other, 'admin_info', 'use_channel')), created_at, type = 2) AS try_cnt,
    argMaxIf(JSONExtractString(other, 'error_type'), created_at, type = 5) AS error_type,
    argMaxIf(JSONExtractUInt(other, 'status_code'), created_at, type = 5) AS status_code,
    argMaxIf(substr(content, 1, 300), created_at, type = 5) AS error_msg
  FROM src
  GROUP BY request_id
)`
}

function outerWhere(f) {
  const w = []
  if (f.channels?.length) w.push(`channel_id IN (${f.channels.map(Number).join(',')})`)
  if (f.keys?.length) {
    const tuples = f.keys.map((k) => {
      const [c, i] = String(k).split(':')
      return `(${Number(c)},${Number(i)})`
    })
    w.push(`(channel_id, key_idx) IN (${tuples.join(',')})`)
  }
  return w.length ? 'WHERE ' + w.join('\n  AND ') : ''
}

// ---------- KPI 总览 ----------
export function kpiQuery(f) {
  const genOk = `ok AND ${GEN_MS} > 0`
  return `${buildReqs(f)}
SELECT
  count() AS total,
  countIf(ok) AS ok_cnt,
  round(countIf(ok) / count() * 100, 2) AS success_rate,
  ${safe("quantileIf(0.5)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p50,
  ${safe("quantileIf(0.95)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p95,
  ${safe("quantileIf(0.99)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p99,
  ${safe(`round(sumIf(completion_tokens, ${genOk}) / (sumIf(${GEN_MS}, ${genOk}) / 1000), 2)`, `sumIf(${GEN_MS}, ${genOk})`)} AS tps,
  ${safe('round(avgIf(use_time_s, ok), 2)', 'countIf(ok)')} AS avg_use_time,
  ${safe('round(sumIf(cache_tokens, ok) / sumIf(prompt_tokens, ok) * 100, 2)', 'sumIf(prompt_tokens, ok)')} AS cache_rate,
  countIf(NOT ok) AS err_cnt,
  countIf(try_cnt > 1) AS retried_cnt
FROM reqs
${outerWhere(f)}`
}

// ---------- 时间趋势 ----------
export function trendQuery(f, gran) {
  const bucket =
    gran === 'minute'
      ? "toStartOfMinute(toDateTime(ts, 'Asia/Shanghai'))"
      : gran === 'hour'
        ? "toStartOfHour(toDateTime(ts, 'Asia/Shanghai'), 'Asia/Shanghai')"
        : "toStartOfDay(toDateTime(ts, 'Asia/Shanghai'), 'Asia/Shanghai')"
  const genOk = `ok AND ${GEN_MS} > 0`
  return `${buildReqs(f)}
SELECT
  ${bucket} AS t,
  count() AS total,
  countIf(ok) AS ok_cnt,
  countIf(NOT ok) AS err_cnt,
  ${safe("quantileIf(0.5)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p50,
  ${safe("quantileIf(0.95)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p95,
  ${safe("quantileIf(0.99)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p99,
  ${safe(`round(sumIf(completion_tokens, ${genOk}) / (sumIf(${GEN_MS}, ${genOk}) / 1000), 2)`, `sumIf(${GEN_MS}, ${genOk})`)} AS tps,
  ${safe('round(sumIf(cache_tokens, ok) / sumIf(prompt_tokens, ok) * 100, 2)', 'sumIf(prompt_tokens, ok)')} AS cache_rate
FROM reqs
${outerWhere(f)}
GROUP BY t ORDER BY t`
}

// ---------- 维度明细表 ----------
export const GROUP_DIMS = {
  channel: { expr: 'channel_id', label: '渠道' },
  key: { expr: '(channel_id, key_idx)', label: 'Key' },
  model: { expr: 'model_name', label: '模型' },
  user: { expr: 'username', label: '用户' },
  token: { expr: 'token_name', label: '令牌' },
  group: { expr: '`group`', label: '分组' },
}

export function dimQuery(f, groupBy) {
  const dim = GROUP_DIMS[groupBy] || GROUP_DIMS.channel
  const genOk = `ok AND ${GEN_MS} > 0`
  return `${buildReqs(f)}
SELECT
  ${dim.expr} AS dim,
  count() AS total,
  countIf(ok) AS ok_cnt,
  round(countIf(ok) / count() * 100, 2) AS success_rate,
  ${safe("quantileIf(0.5)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p50,
  ${safe("quantileIf(0.95)(frt_ms, ok AND frt_ms > 0)", 'countIf(ok AND frt_ms > 0)')} AS frt_p95,
  ${safe(`round(sumIf(completion_tokens, ${genOk}) / (sumIf(${GEN_MS}, ${genOk}) / 1000), 2)`, `sumIf(${GEN_MS}, ${genOk})`)} AS tps,
  ${safe('round(avgIf(use_time_s, ok), 2)', 'countIf(ok)')} AS avg_use_time,
  ${safe('round(sumIf(cache_tokens, ok) / sumIf(prompt_tokens, ok) * 100, 2)', 'sumIf(prompt_tokens, ok)')} AS cache_rate,
  countIf(NOT ok) AS err_cnt,
  countIf(try_cnt > 1) AS retried_cnt
FROM reqs
${outerWhere(f)}
GROUP BY dim ORDER BY total DESC`
}

// ---------- 报错 ----------
export function errDistQuery(f) {
  return `${buildReqs(f)}
SELECT error_type, toString(status_code) AS status_code, count() AS cnt
FROM reqs
${outerWhere(f) ? outerWhere(f) + ' AND ' : 'WHERE '}NOT ok
GROUP BY error_type, status_code ORDER BY cnt DESC`
}

export function errListQuery(f, limit = 50) {
  return `${buildReqs(f)}
SELECT
  toString(ts) AS ts,
  channel_id, model_name, username, token_name,
  error_type, toString(status_code) AS status_code,
  error_msg, request_id, try_cnt
FROM reqs
${outerWhere(f) ? outerWhere(f) + ' AND ' : 'WHERE '}NOT ok
ORDER BY ts DESC
LIMIT ${limit}`
}

// ---------- 渠道 × 日期 热力图 ----------
export function heatQuery(f) {
  return `${buildReqs(f)}
SELECT
  channel_id,
  toDate(toDateTime(ts, 'Asia/Shanghai'), 'Asia/Shanghai') AS d,
  count() AS cnt,
  countIf(NOT ok) AS err_cnt
FROM reqs
${outerWhere(f)}
GROUP BY channel_id, d`
}

// ---------- 筛选项下拉选项 ----------
export function optionsQuery(t0, t1) {
  return `SELECT
  groupUniqArray(10000)(channel_id) AS channels,
  groupUniqArray(10000)(model_name) AS models,
  groupUniqArray(10000)(username) AS users,
  groupUniqArray(10000)(token_name) AS tokens,
  groupUniqArray(10000)(\`group\`) AS groups
FROM new_api_logs.logs
WHERE type IN (2, 5) AND request_id != ''
  AND created_at >= ${Math.floor(t0)} AND created_at < ${Math.floor(t1)}`
}

export function keyOptionsQuery(t0, t1) {
  return `SELECT groupUniqArray(10000)(tuple(channel_id, JSONExtractInt(other, 'admin_info', 'multi_key_index'))) AS keys
FROM new_api_logs.logs
WHERE type = 2 AND JSONHas(other, 'admin_info', 'multi_key_index')
  AND created_at >= ${Math.floor(t0)} AND created_at < ${Math.floor(t1)}`
}

// ---------- 数据时间范围 ----------
export function timeRangeQuery() {
  return `SELECT toString(min(created_at)) AS t0, toString(max(created_at)) AS t1
FROM new_api_logs.logs WHERE type IN (2, 5)`
}
