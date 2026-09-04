// 全量 SQL 构造器验证：把 src/api/sql.js 的每条查询经真实链路（/ch 代理 -> 桥接/CH）跑一遍。
// 用法: node scripts/validate_queries.mjs [--base http://localhost:5173/ch]
// 背景: 2026-09-03 optionsQuery 数组列 bug 漏网，就是因为当年只测了 kpi/dim/errdist/heat。
//       以后新增任何 SQL 构造器，必须加进本脚本并跑通。
import * as sql from '../src/api/sql.js'

const BASE = process.argv.includes('--base')
  ? process.argv[process.argv.indexOf('--base') + 1]
  : 'http://localhost:5173/ch/'

const t = Math.floor(Date.now() / 1000)
const f = { t0: t - 7 * 86400, t1: t, channels: [], keys: [], users: [], models: [], tokens: [], groups: [] }

// 取真实数据构造"全部筛选项组合"用例（防 WHERE 别名遮蔽类 bug 回归）
const opt = (await (await fetch(BASE, { method: 'POST', body: sql.optionsQuery(f.t0, f.t1) })).json()).data[0] || {}
const pick = (a) => (Array.isArray(a) && a.length ? [a[a.length > 1 ? 1 : 0]] : [])
const fAll = {
  ...f,
  channels: opt.channels || [],
  users: pick(opt.users),
  models: pick(opt.models),
  tokens: pick(opt.tokens),
  groups: pick(opt.groups),
  keys: [], // keyOptions 可能为空，有值时取第一个
}
const keysOpt = (await (await fetch(BASE, { method: 'POST', body: sql.keyOptionsQuery(f.t0, f.t1) })).json()).data[0] || {}
if (Array.isArray(keysOpt.keys) && keysOpt.keys.length) {
  const k = keysOpt.keys[0]
  fAll.keys = [Array.isArray(k) ? k[0] + ':' + k[1] : String(k)]
}

const TESTS = [
  ['kpi', sql.kpiQuery(f)],
  ['kpi_filtered', sql.kpiQuery({ ...f, channels: [8, 9], keys: ['8:2'] })],
  // 全筛选组合：users/models/tokens/groups 走 CTE 行级过滤（曾因 CH 别名遮蔽崩溃）
  ['kpi_all_filters', sql.kpiQuery(fAll)],
  ['trend_all_filters', sql.trendQuery(fAll, 'hour')],
  ['dim_channel_all_filters', sql.dimQuery(fAll, 'channel')],
  ['dim_model_all_filters', sql.dimQuery(fAll, 'model')],
  ['errDist_all_filters', sql.errDistQuery(fAll)],
  ['errList_all_filters', sql.errListQuery(fAll)],
  ['trend_hour', sql.trendQuery(f, 'hour')],
  ['trend_day', sql.trendQuery(f, 'day')],
  ['dim_channel', sql.dimQuery(f, 'channel')],
  ['dim_key', sql.dimQuery(f, 'key')],
  ['dim_user', sql.dimQuery(f, 'user')],
  ['dim_model', sql.dimQuery(f, 'model')],
  ['dim_token', sql.dimQuery(f, 'token')],
  ['dim_group', sql.dimQuery(f, 'group')],
  ['errDist', sql.errDistQuery(f)],
  ['errList', sql.errListQuery(f)],
  ['heat', sql.heatQuery(f)],
  ['options', sql.optionsQuery(f.t0, f.t1)],
  ['keyOptions', sql.keyOptionsQuery(f.t0, f.t1)],
  ['timeRange', sql.timeRangeQuery()],
]

let fail = 0
for (const [name, q] of TESTS) {
  try {
    const res = await fetch(BASE, { method: 'POST', body: q })
    const text = await res.text()
    if (!res.ok) {
      fail++
      console.error(`FAIL ${name.padEnd(14)} ${res.status} ${text.slice(0, 160)}`)
      continue
    }
    const j = JSON.parse(text)
    console.log(`ok   ${name.padEnd(14)} rows=${j.rows}`)
  } catch (e) {
    fail++
    console.error(`FAIL ${name.padEnd(14)} ${e.message}`)
  }
}

// 类型断言：options/keyOptions 的数组列必须是真数组（防桥接/CH 序列化回归）
const asserts = [
  ['options.channels is Array', Array.isArray(opt.channels)],
  ['options.models is Array', Array.isArray(opt.models)],
  ['options.users is Array', Array.isArray(opt.users)],
  ['options.tokens is Array', Array.isArray(opt.tokens)],
  ['options.groups is Array', Array.isArray(opt.groups)],
  ['keyOptions.keys is Array', Array.isArray(keysOpt.keys)],
]
for (const [name, pass] of asserts) {
  console.log(`${pass ? 'ok  ' : 'FAIL'} ${name}`)
  if (!pass) fail++
}

console.log(fail ? `\n${fail} 项失败` : '\n全部通过')
process.exit(fail ? 1 : 0)
