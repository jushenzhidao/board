<script setup>
// 趋势图三组：请求量+成功率 / FRT 分位数 / TPS+缓存
import { computed } from 'vue'
import dayjs from 'dayjs'
import EChart from './EChart.vue'

const props = defineProps({
  trend: { type: Array, default: () => [] },
  gran: { type: String, default: 'day' },
})

const C = { blue: '#2563eb', green: '#059669', red: '#dc2626', amber: '#d97706', gray: '#94a3b8', purple: '#7c3aed' }

const labels = computed(() => props.trend.map((r) => r.t))
const labelFmt = (v) => (props.gran === 'day' ? dayjs(v).format('MM-DD') : dayjs(v).format('MM-DD HH:mm'))

const baseAxis = (extra = {}) => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 50, right: 50, top: 30, bottom: 30 },
  xAxis: { type: 'category', data: labels.value, axisLabel: { formatter: labelFmt } },
  ...extra,
})

const opt1 = computed(() =>
  baseAxis({
    yAxis: [
      { type: 'value', name: '请求数', minInterval: 1 },
      { type: 'value', name: '成功率%', max: 100, min: 0, splitLine: { show: false } },
    ],
    series: [
      {
        name: '请求数', type: 'bar', barMaxWidth: 28,
        data: props.trend.map((r) => r.total), itemStyle: { color: C.blue },
      },
      {
        name: '失败数', type: 'bar', barMaxWidth: 28, stack: 'x',
        data: props.trend.map((r) => r.err_cnt), itemStyle: { color: C.red },
      },
      {
        name: '成功率', type: 'line', yAxisIndex: 1, smooth: true,
        data: props.trend.map((r) => (r.total ? +((r.ok_cnt / r.total) * 100).toFixed(2) : null)),
        itemStyle: { color: C.green }, lineStyle: { width: 2 },
      },
    ],
  }),
)

const opt2 = computed(() =>
  baseAxis({
    yAxis: { type: 'value', name: 'ms', axisLabel: { formatter: (v) => (v >= 1000 ? v / 1000 + 's' : v) } },
    series: [
      { name: 'P50', type: 'line', smooth: true, data: props.trend.map((r) => r.frt_p50), itemStyle: { color: C.blue } },
      { name: 'P95', type: 'line', smooth: true, data: props.trend.map((r) => r.frt_p95), itemStyle: { color: C.amber } },
      { name: 'P99', type: 'line', smooth: true, data: props.trend.map((r) => r.frt_p99), itemStyle: { color: C.red } },
    ],
  }),
)

const opt3 = computed(() =>
  baseAxis({
    yAxis: [
      { type: 'value', name: 'TPS' },
      { type: 'value', name: '缓存命中%', max: 100, min: 0, splitLine: { show: false } },
    ],
    series: [
      { name: 'TPS', type: 'line', smooth: true, data: props.trend.map((r) => r.tps), itemStyle: { color: C.purple } },
      {
        name: '缓存命中率', type: 'line', smooth: true, yAxisIndex: 1,
        data: props.trend.map((r) => r.cache_rate), itemStyle: { color: C.green },
      },
    ],
  }),
)
</script>

<template>
  <div class="grid-charts">
    <div class="panel">
      <div class="chart-title">请求量 & 成功率</div>
      <EChart :option="opt1" height="250px" />
    </div>
    <div class="panel">
      <div class="chart-title">FRT 分位数（首字延迟）</div>
      <EChart :option="opt2" height="250px" />
    </div>
    <div class="panel">
      <div class="chart-title">TPS & 缓存命中率</div>
      <EChart :option="opt3" height="250px" />
    </div>
  </div>
</template>
