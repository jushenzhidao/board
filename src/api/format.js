import dayjs from 'dayjs'

export function fmtNum(v, digits = 0) {
  if (v === null || v === undefined || v === '' || Number.isNaN(v)) return '-'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: digits })
}

// 大数缩写：>=1B 用 B、>=1M 用 M、>=1K 用 K，否则原样
export function fmtBigNum(v) {
  if (v === null || v === undefined || v === '' || Number.isNaN(v)) return '-'
  const n = Number(v)
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

export function fmtPct(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2) + '%'
}

// 消费金额：new-api 的 quota（额度）按 QuotaPerUnit 换算成货币。
// quotaPerUnit = 1 个货币单位等于多少 quota（new-api 默认 500000，即 $1 = 500000）。
export function toMoney(quota, perUnit = 500000) {
  if (quota === null || quota === undefined || quota === '') return null
  const n = Number(quota)
  const u = Number(perUnit)
  if (!Number.isFinite(n) || !Number.isFinite(u) || u <= 0) return null
  return n / u
}

export function fmtMoney(quota, perUnit = 500000, symbol = '$') {
  const v = toMoney(quota, perUnit)
  if (v === null) return '-'
  const abs = Math.abs(v)
  // 金额较小时多留 2 位，避免「$0.00」看不出消耗
  const digits = abs > 0 && abs < 1 ? 4 : 2
  return (
    symbol +
    v.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
  )
}

export function fmtMs(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  const n = Number(v)
  if (n >= 60000) return (n / 60000).toFixed(1) + ' 分钟'
  if (n >= 1000) return (n / 1000).toFixed(2) + ' s'
  return Math.round(n) + ' ms'
}

export function fmtSec(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return Number(v).toFixed(1) + ' s'
}

export function fmtTps(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return Number(v).toFixed(1)
}

// CH 返回 "YYYY-MM-DD HH:MM:SS"（Asia/Shanghai 墙上时间）
export function fmtTime(s, gran) {
  if (!s) return '-'
  return gran === 'day' ? dayjs(s).format('MM-DD') : dayjs(s).format('MM-DD HH:mm')
}

export function fmtFullTime(unixSec) {
  if (!unixSec) return '-'
  return dayjs(Number(unixSec) * 1000).format('YYYY-MM-DD HH:mm:ss')
}

// 环比：返回 { pct: 数值或 null, good: 方向是否向好 }
export function deltaOf(cur, prev, higherIsBetter) {
  if (cur === null || prev === null || prev === undefined || Number.isNaN(cur) || Number.isNaN(prev)) {
    return { pct: null }
  }
  if (prev === 0) return { pct: null }
  const pct = Number((((cur - prev) / Math.abs(prev)) * 100).toFixed(1))
  return { pct, good: higherIsBetter ? pct >= 0 : pct <= 0 }
}
