import dayjs from 'dayjs'

export function fmtNum(v, digits = 0) {
  if (v === null || v === undefined || v === '' || Number.isNaN(v)) return '-'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: digits })
}

export function fmtPct(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return Number(v).toFixed(2) + '%'
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
