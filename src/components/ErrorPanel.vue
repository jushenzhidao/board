<script setup>
// 报错分析：类型分布 + 最终失败明细
import { computed } from 'vue'
import dayjs from 'dayjs'
import EChart from './EChart.vue'
import { fmtFullTime, fmtNum } from '../api/format.js'

const props = defineProps({
  dist: { type: Array, default: () => [] },
  list: { type: Array, default: () => [] },
  channelName: { type: Function, required: true },
})

const total = computed(() => props.dist.reduce((s, r) => s + Number(r.cnt), 0))

const opt = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 120, right: 40, top: 10, bottom: 30 },
  xAxis: { type: 'value', minInterval: 1 },
  yAxis: {
    type: 'category',
    data: props.dist.map((r) => `${r.error_type || '-'} ${r.status_code || ''}`),
  },
  series: [
    {
      type: 'bar',
      barMaxWidth: 20,
      data: props.dist.map((r) => Number(r.cnt)),
      itemStyle: { color: '#dc2626' },
      label: { show: true, position: 'right' },
    },
  ],
}))
</script>

<template>
  <div class="grid-charts">
    <div class="panel">
      <div class="chart-title">报错分布（最终失败请求，共 {{ fmtNum(total) }}）</div>
      <EChart :option="opt" height="240px" />
    </div>
    <div class="panel">
      <div class="chart-title">报错明细（最近 50 条）</div>
      <div style="overflow: auto; max-height: 260px">
        <table class="tbl error-detail">
          <thead>
            <tr><th style="text-align:left">时间</th><th>渠道</th><th style="text-align:left">模型</th><th>类型</th><th>码</th><th style="text-align:left">错误信息</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in list" :key="i">
              <td class="num muted">{{ fmtFullTime(r.ts) }}</td>
              <td>{{ channelName(r.channel_id) || 'ID ' + r.channel_id }}</td>
              <td>{{ r.model_name }}</td>
              <td>{{ r.error_type || '-' }}</td>
              <td class="num"><span class="tag red">{{ r.status_code || '-' }}</span></td>
              <td class="muted" :title="r.error_msg">{{ (r.error_msg || '').slice(0, 90) }}</td>
            </tr>
            <tr v-if="!list.length"><td colspan="6" class="muted" style="text-align:center;padding:16px">所选范围内无最终失败请求 🎉</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
