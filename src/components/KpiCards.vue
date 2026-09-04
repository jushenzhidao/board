<script setup>
// KPI 指标卡 ×7（含环比）
import { computed } from 'vue'
import { fmtNum, fmtPct, fmtMs, fmtTps, fmtSec, deltaOf } from '../api/format.js'

const props = defineProps({
  kpi: { type: Object, default: null },
  kpiPrev: { type: Object, default: null },
})

const cards = computed(() => {
  const k = props.kpi || {}
  const p = props.kpiPrev || {}
  const d = (cur, prev, hib) => deltaOf(cur, prev, hib)
  const sub = (cur, prev, hib, suffix = '') => {
    const r = d(cur, prev, hib)
    if (r.pct === null) return ''
    return { cls: r.good ? 'delta-up' : 'delta-down', text: (r.pct > 0 ? '+' : '') + r.pct + '%' + suffix }
  }
  return [
    {
      label: '请求数',
      value: fmtNum(k.total),
      sub2: `成功 ${fmtNum(k.ok_cnt)} / 失败 ${fmtNum(k.err_cnt)}`,
      delta: sub(k.total, p.total, true),
    },
    {
      label: '成功率（最终结果）',
      value: fmtPct(k.success_rate),
      sub2: k.retried_cnt ? `重试请求 ${k.retried_cnt}` : '重试排除口径',
      delta: sub(k.success_rate, p.success_rate, true),
    },
    {
      label: 'FRT P95',
      value: fmtMs(k.frt_p95),
      sub2: `P50 ${fmtMs(k.frt_p50)}`,
      delta: sub(k.frt_p95, p.frt_p95, false),
    },
    {
      label: 'TPS',
      value: fmtTps(k.tps),
      sub2: '输出 token/秒，加权',
      delta: sub(k.tps, p.tps, true),
    },
    {
      label: '平均耗时',
      value: fmtSec(k.avg_use_time),
      sub2: 'use_time 均值',
      delta: sub(k.avg_use_time, p.avg_use_time, false),
    },
    {
      label: '缓存命中率',
      value: fmtPct(k.cache_rate),
      sub2: 'cache_tokens / 输入 token',
      delta: sub(k.cache_rate, p.cache_rate, true),
    },
    {
      label: '报错数',
      value: fmtNum(k.err_cnt),
      sub2: '最终失败请求',
      delta: sub(k.err_cnt, p.err_cnt, false),
    },
  ]
})
</script>

<template>
  <div class="grid-kpi">
    <div v-for="c in cards" :key="c.label" class="kpi-card" :class="{ 'up-is-bad': false }">
      <div class="k-label">{{ c.label }}</div>
      <div class="k-value">{{ c.value }}</div>
      <div class="k-sub">
        <span v-if="c.delta" :class="c.delta.cls">{{ c.delta.text }}</span>
        <span>{{ c.sub2 }}</span>
      </div>
    </div>
  </div>
</template>
