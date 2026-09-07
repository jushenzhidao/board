<script setup>
// KPI 指标卡 ×8（含环比）
import { computed } from 'vue'
import { fmtNum, fmtPct, fmtMs, fmtTps, fmtSec, fmtBigNum, deltaOf } from '../api/format.js'

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
      label: 'Token 用量',
      kind: 'tokens',
      value: fmtBigNum(k.total_tok),
      delta: sub(k.total_tok, p.total_tok, true),
      tokens: [
        { label: '缓存', val: fmtBigNum(k.cache_tok) },
        { label: '输入', val: fmtBigNum(k.input_tok) },
        { label: '输出', val: fmtBigNum(k.output_tok) },
        { label: '总', val: fmtBigNum(k.total_tok) },
      ],
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
    <div v-for="c in cards" :key="c.label" class="kpi-card" :class="{ 'kpi-card-wide': c.kind === 'tokens' }">
      <div class="k-label">{{ c.label }}</div>
      <div class="k-value">{{ c.value }}</div>
      <!-- Token 大卡：2×2 子数字（缓存/输入/输出/总） -->
      <div v-if="c.kind === 'tokens'" class="k-tokens">
        <div v-for="t in c.tokens" :key="t.label">
          <span class="tk-label">{{ t.label }}</span>
          <span class="tk-val">{{ t.val }}</span>
        </div>
      </div>
      <div v-else class="k-sub">
        <span v-if="c.delta" :class="c.delta.cls">{{ c.delta.text }}</span>
        <span>{{ c.sub2 }}</span>
      </div>
      <!-- Token 大卡环比独立显示在底部 -->
      <div v-if="c.kind === 'tokens'" class="k-sub k-sub-extra">
        <span v-if="c.delta" :class="c.delta.cls">{{ c.delta.text }}</span>
        <span>环比</span>
      </div>
    </div>
  </div>
</template>
