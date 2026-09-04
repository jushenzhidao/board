<script setup>
// ECharts 容器组件：初始化 / 更新 / 自适应 / 销毁
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '260px' },
})

const el = ref(null)
let chart = null
let ro = null

onMounted(() => {
  chart = echarts.init(el.value)
  chart.setOption(props.option)
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})

watch(
  () => props.option,
  (opt) => chart && chart.setOption(opt, true),
  { deep: false },
)

onBeforeUnmount(() => {
  ro && ro.disconnect()
  chart && chart.dispose()
  chart = null
})
</script>

<template>
  <div ref="el" class="chart-box" :style="{ height }"></div>
</template>
