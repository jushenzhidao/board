<script setup>
// 筛选栏：时间 / 渠道 / Key / 用户 / 模型 / 令牌 / 分组 + 分组依据
import { computed } from 'vue'
import dayjs from 'dayjs'
import FSelect from './FSelect.vue'

const props = defineProps({
  state: { type: Object, required: true }, // {t0,t1,channels,keys,users,models,tokens,groups,groupBy}
  options: { type: Object, default: () => ({}) }, // {channels:[],models:[],users:[],tokens:[],groups:[],keys:[]}
  channelName: { type: Function, required: true }, // id -> name
})
const emit = defineEmits(['refresh'])

const SHORTCUTS = [
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '3d', hours: 72 },
  { label: '7d', hours: 168 },
  { label: '14d', hours: 336 },
  { label: '30d', hours: 720 },
]
const GROUP_BYS = [
  { value: 'channel', label: '渠道' },
  { value: 'key', label: 'Key' },
  { value: 'model', label: '模型' },
  { value: 'user', label: '用户' },
  { value: 'token', label: '令牌' },
  { value: 'group', label: '分组' },
]

const activeShortcut = computed(
  () => SHORTCUTS.find((s) => s.hours === (props.state.t1 - props.state.t0) / 3600)?.label || null,
)

function applyShortcut(h) {
  props.state.t1 = Math.floor(Date.now() / 1000)
  props.state.t0 = props.state.t1 - h * 3600
}

const customStart = computed({
  get: () => dayjs(props.state.t0 * 1000).format('YYYY-MM-DDTHH:mm'),
  set: (v) => { if (v) props.state.t0 = dayjs(v).unix() },
})
const customEnd = computed({
  get: () => dayjs(props.state.t1 * 1000).format('YYYY-MM-DDTHH:mm'),
  set: (v) => { if (v) props.state.t1 = dayjs(v).unix() },
})

function keyLabel(k) {
  // k = "channelId:keyIdx"
  const [c, i] = String(k).split(':')
  return (props.channelName(Number(c)) || 'ID ' + c) + ' · K' + i
}
</script>

<template>
  <div class="panel">
    <div class="filter-bar">
      <div class="filter-item shortcut">
        <label>时间</label>
        <button
          v-for="s in SHORTCUTS" :key="s.label" type="button"
          :class="{ on: activeShortcut === s.label }"
          @click="applyShortcut(s.hours)"
        >{{ s.label }}</button>
        <button type="button" title="按数据实际时间范围查询" @click="emit('all')">全部</button>
      </div>
      <div class="filter-item">
        <input type="datetime-local" v-model="customStart" /> ~
        <input type="datetime-local" v-model="customEnd" />
      </div>
    </div>

    <div class="filter-bar" style="margin-top: 10px">
      <div class="filter-item">
        <label>渠道</label>
        <FSelect v-model="state.channels"
          :options="(options.channels || []).map((c) => ({ value: c, label: channelName(c) || 'ID ' + c }))" />
      </div>
      <div class="filter-item">
        <label>Key</label>
        <FSelect v-model="state.keys"
          :options="(options.keys || []).map((k) => ({ value: k, label: keyLabel(k) }))" />
      </div>
      <div class="filter-item">
        <label>用户</label>
        <FSelect v-model="state.users"
          :options="(options.users || []).map((u) => ({ value: u, label: u }))" />
      </div>
      <div class="filter-item">
        <label>模型</label>
        <FSelect v-model="state.models"
          :options="(options.models || []).map((m) => ({ value: m, label: m }))" />
      </div>
      <div class="filter-item">
        <label>令牌</label>
        <FSelect v-model="state.tokens"
          :options="(options.tokens || []).map((t) => ({ value: t, label: t }))" />
      </div>
      <div class="filter-item">
        <label>分组</label>
        <FSelect v-model="state.groups"
          :options="(options.groups || []).map((g) => ({ value: g, label: g || '(空)' }))" />
      </div>
    </div>

    <div class="filter-bar" style="margin-top: 10px">
      <div class="filter-item">
        <label>分组依据</label>
        <div class="seg">
          <button v-for="g in GROUP_BYS" :key="g.value" type="button"
            :class="{ on: state.groupBy === g.value }"
            @click="state.groupBy = g.value">{{ g.label }}</button>
        </div>
      </div>
      <div class="spacer" style="flex: 1"></div>
      <button class="primary" type="button" @click="emit('refresh')">刷新</button>
    </div>
  </div>
</template>
