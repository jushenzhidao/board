<script setup>
// 渠道 × 日期 请求量热力图（红色标记含报错的格子）
import { computed } from 'vue'
import EChart from './EChart.vue'

const props = defineProps({
  heat: { type: Array, default: () => [] }, // [{channel_id, d, cnt, err_cnt}]
  channels: { type: Array, default: () => [] }, // 有数据的 channel_id 列表
  channelName: { type: Function, required: true },
})

const dates = computed(() => [...new Set(props.heat.map((r) => r.d))].sort())
const rows = computed(() => props.channels)

const key = (ch, d) => ch + '|' + d
const map = computed(() => {
  const m = {}
  for (const r of props.heat) m[key(r.channel_id, r.d)] = r
  return m
})
const maxCnt = computed(() => Math.max(1, ...props.heat.map((r) => Number(r.cnt))))

const opt = computed(() => ({
  tooltip: {
    formatter: (p) => {
      const r = map.value[p.data[1] + '|' + dates.value[p.data[0]]]
      if (!r) return ''
      const name = props.channelName(r.channel_id) || 'ID ' + r.channel_id
      return `${name} · ${r.d}<br/>请求数: ${r.cnt}${Number(r.err_cnt) ? '<br/>报错: <b style="color:#dc2626">' + r.err_cnt + '</b>' : ''}`
    },
  },
  grid: { left: 110, right: 40, top: 10, bottom: 60 },
  xAxis: { type: 'category', data: dates.value },
  yAxis: {
    type: 'category',
    data: rows.value.map((c) => props.channelName(c) || 'ID ' + c),
  },
  visualMap: {
    min: 0, max: maxCnt.value, orient: 'horizontal', left: 'center', bottom: 0,
    inRange: { color: ['#eff6ff', '#bfdbfe', '#60a5fa', '#2563eb', '#1e3a8a'] },
  },
  series: [
    {
      type: 'heatmap',
      data: (() => {
        const out = []
        dates.value.forEach((d, xi) => {
          rows.value.forEach((c, yi) => {
            const r = map.value[key(c, d)]
            if (r && Number(r.cnt) > 0) out.push([xi, yi, Number(r.cnt), Number(r.err_cnt)])
          })
        })
        return out
      })(),
      label: { show: false },
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 2,
      },
    },
  ],
}))
</script>

<template>
  <div class="panel">
    <div class="chart-title">渠道 × 日期 请求量热力图（悬停查看，红色边框标记含报错）</div>
    <EChart :option="opt" height="240px" />
  </div>
</template>
