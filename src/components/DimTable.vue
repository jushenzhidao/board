<script setup>
// 维度明细表：按分组依据聚合，可排序，点击行下钻
import { ref, computed } from 'vue'
import { fmtNum, fmtPct, fmtMs, fmtTps, fmtSec } from '../api/format.js'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  groupBy: { type: String, default: 'channel' },
  dimLabel: { type: Function, required: true }, // dim原始值 -> 显示名
})
const emit = defineEmits(['drill'])

const sortKey = ref('total')
const sortAsc = ref(false)

const COLS = [
  { key: 'total', label: '请求数', fmt: (v) => fmtNum(v) },
  { key: 'ok_cnt', label: '成功', fmt: (v) => fmtNum(v) },
  { key: 'err_cnt', label: '报错', fmt: (v) => fmtNum(v) },
  { key: 'success_rate', label: '成功率', fmt: (v) => fmtPct(v) },
  { key: 'frt_p50', label: 'FRT P50', fmt: (v) => fmtMs(v) },
  { key: 'frt_p95', label: 'FRT P95', fmt: (v) => fmtMs(v) },
  { key: 'tps', label: 'TPS', fmt: (v) => fmtTps(v) },
  { key: 'avg_use_time', label: '平均耗时', fmt: (v) => fmtSec(v) },
  { key: 'cache_rate', label: '缓存率', fmt: (v) => fmtPct(v) },
  { key: 'retried_cnt', label: '重试数', fmt: (v) => fmtNum(v) },
]

const sorted = computed(() => {
  const arr = [...props.rows]
  const k = sortKey.value
  arr.sort((a, b) => {
    const av = a[k] ?? -Infinity
    const bv = b[k] ?? -Infinity
    return (sortAsc.value ? 1 : -1) * (av > bv ? 1 : av < bv ? -1 : 0)
  })
  return arr
})

function setSort(k) {
  if (sortKey.value === k) sortAsc.value = !sortAsc.value
  else { sortKey.value = k; sortAsc.value = false }
}

function rate(row, col) {
  if (row.total) return row[col.key]
  return null
}
</script>

<template>
  <div class="panel">
    <div class="chart-title" style="margin-bottom: 8px">
      维度明细（按{{ { channel: '渠道', key: 'Key', model: '模型', user: '用户', token: '令牌', group: '分组' }[groupBy] }}聚合，点击行下钻）
    </div>
    <div style="overflow: auto; max-height: 480px">
      <table class="tbl">
        <thead>
          <tr>
            <th @click="setSort('dim')">
              {{ { channel: '渠道', key: 'Key', model: '模型', user: '用户', token: '令牌', group: '分组' }[groupBy] }}
            </th>
            <th v-for="c in COLS" :key="c.key" :class="{ sorted: sortKey === c.key }" @click="setSort(c.key)">
              {{ c.label }}{{ sortKey === c.key ? (sortAsc ? ' ↑' : ' ↓') : '' }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in sorted" :key="String(r.dim)" @click="emit('drill', { groupBy, dim: r.dim })">
            <td>{{ dimLabel(groupBy, r.dim) }}</td>
            <td v-for="c in COLS" :key="c.key" class="num">
              <template v-if="c.key === 'success_rate'">
                <span :class="rate(r, c) === null ? 'muted' : rate(r, c) >= 99 ? 'delta-up' : rate(r, c) >= 90 ? '' : 'delta-down'">
                  {{ c.fmt(rate(r, c)) }}
                </span>
              </template>
              <template v-else-if="c.key === 'err_cnt'">
                <span :class="r.err_cnt > 0 ? 'delta-down' : 'muted'">{{ c.fmt(r.err_cnt) }}</span>
              </template>
              <template v-else>{{ c.fmt(r[c.key]) }}</template>
            </td>
          </tr>
          <tr v-if="!sorted.length"><td :colspan="COLS.length + 1" class="muted" style="text-align: center; padding: 20px">无数据</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
