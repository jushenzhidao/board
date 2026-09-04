<script setup>
// 通用下拉多选（带搜索）
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] }, // [{value, label}]
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const keyword = ref('')
const root = ref(null)

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return props.options
  return props.options.filter((o) => String(o.label).toLowerCase().includes(kw))
})

const selected = computed(() => new Set(props.modelValue.map(String)))

const btnText = computed(() => {
  if (!props.modelValue.length) return '全部'
  if (props.modelValue.length === 1) {
    const opt = props.options.find((o) => String(o.value) === String(props.modelValue[0]))
    return opt ? opt.label : props.modelValue[0]
  }
  return `已选 ${props.modelValue.length} 项`
})

function toggle(v) {
  const s = new Set(props.modelValue.map(String))
  const key = String(v)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  emit('update:modelValue', [...s])
}

function clearAll() {
  keyword.value = ''
  emit('update:modelValue', [])
}

function onClickDoc(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onClickDoc))
onBeforeUnmount(() => document.removeEventListener('click', onClickDoc))
</script>

<template>
  <div class="fsel" ref="root">
    <button class="fsel-btn" type="button" @click="open = !open">
      <span :style="modelValue.length ? 'color:var(--accent)' : ''">{{ btnText }}</span>
      <span class="caret">▼</span>
    </button>
    <div v-if="open" class="fsel-pop">
      <input class="search" type="text" v-model="keyword" placeholder="搜索…" />
      <div class="fsel-list">
        <label v-for="o in filtered" :key="o.value">
          <input type="checkbox" :checked="selected.has(String(o.value))" @change="toggle(o.value)" />
          <span>{{ o.label }}</span>
        </label>
        <div v-if="!filtered.length" class="muted" style="padding: 6px">无选项</div>
      </div>
      <div class="fsel-actions">
        <button type="button" @click="clearAll">清空</button>
        <button type="button" @click="open = false">确定</button>
      </div>
    </div>
  </div>
</template>
