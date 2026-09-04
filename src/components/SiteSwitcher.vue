<script setup>
// 站点切换器：下拉列出所有站点（点击切换），底部「新增站点」，每项可编辑/删除
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  sites: { type: Array, default: () => [] },
  value: { type: String, default: '' },
})
const emit = defineEmits(['change', 'add', 'edit', 'delete'])

const open = ref(false)
const root = ref(null)

const current = computed(() => props.sites.find((s) => s.id === props.value))

function toggle() { open.value = !open.value }
function close() { open.value = false }

function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) close()
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

function pick(s) {
  close()
  if (s.id !== props.value) emit('change', s.id)
}
</script>

<template>
  <div class="ss" ref="root">
    <button type="button" class="ss-btn" :title="current?.name || '切换站点'" @click="toggle">
      <span class="ss-name">{{ current?.name || '选择站点' }}</span>
      <span class="caret">▾</span>
    </button>

    <div class="ss-pop" v-if="open">
      <div class="ss-list">
        <div v-for="s in sites" :key="s.id" class="ss-item" :class="{ on: s.id === value }" @click="pick(s)">
          <span class="ss-item-name">{{ s.name }}</span>
          <span class="ss-item-id">{{ s.id }}</span>
          <span class="ss-ops">
            <button type="button" class="op" title="编辑" @click.stop="close(); emit('edit', s)">✎</button>
            <button type="button" class="op danger" title="删除" @click.stop="close(); emit('delete', s)">🗑</button>
          </span>
        </div>
      </div>
      <div class="ss-foot">
        <button type="button" class="add" @click="close(); emit('add')">＋ 新增站点</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ss { position: relative; }
.ss-btn {
  display: flex; align-items: center; gap: 8px; padding: 4px 10px;
  background: #fff; border: 1px solid var(--border); border-radius: 6px;
  font-size: 13px; cursor: pointer; color: var(--text);
}
.ss-btn:hover { border-color: var(--accent); color: var(--accent); }
.ss-name { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.caret { color: var(--text2); font-size: 11px; }

.ss-pop {
  position: absolute; z-index: 60; top: calc(100% + 4px); right: 0;
  background: #fff; border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 8px 24px rgba(16,24,40,.14); min-width: 240px; overflow: hidden;
}
.ss-list { max-height: 300px; overflow: auto; }
.ss-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px; cursor: pointer;
  font-size: 13px;
}
.ss-item:hover { background: #f3f4f6; }
.ss-item.on { background: var(--accent-weak); }
.ss-item.on .ss-item-name { color: var(--accent); font-weight: 600; }
.ss-item-name { flex: 0 1 auto; }
.ss-item-id { color: var(--text2); font-size: 11px; flex: 1; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ss-ops { display: flex; gap: 2px; opacity: 0; transition: opacity .12s; }
.ss-item:hover .ss-ops { opacity: 1; }
.op {
  border: 0; background: transparent; padding: 2px 5px; font-size: 13px;
  border-radius: 4px; cursor: pointer; color: var(--text2); line-height: 1;
}
.op:hover { background: #e5e9f0; color: var(--accent); }
.op.danger:hover { background: #fef2f2; color: var(--bad); }

.ss-foot { border-top: 1px solid var(--border); padding: 6px; }
.add {
  width: 100%; border: 1px dashed var(--border); background: transparent;
  color: var(--accent); border-radius: 6px; padding: 6px 0; font-size: 13px; cursor: pointer;
}
.add:hover { background: var(--accent-weak); border-color: var(--accent); }
</style>
