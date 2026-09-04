<script setup>
// 访问令牌登录框：服务端 BOARD_TOKEN 启用时，接口 401 后弹出
import { ref } from 'vue'

const emit = defineEmits(['success', 'close'])

const token = ref('')
const err = ref('')

function submit() {
  const t = token.value.trim()
  if (!t) {
    err.value = '令牌不能为空'
    return
  }
  err.value = ''
  emit('success', t)
}
</script>

<template>
  <div class="mask">
    <div class="dialog login-dialog">
      <h3>访问令牌</h3>
      <p class="hint">
        此看板受访问令牌保护，请输入令牌以继续。令牌由服务端环境变量
        <code>BOARD_TOKEN</code> 配置。
      </p>
      <div class="row">
        <label>令牌</label>
        <input
          v-model="token"
          type="password"
          placeholder="请输入访问令牌"
          autocomplete="off"
          autofocus
          @keyup.enter="submit"
        />
      </div>
      <div v-if="err" class="login-err">{{ err }}</div>
      <div class="foot">
        <button type="button" @click="emit('close')">取消</button>
        <button type="button" class="primary" @click="submit">确定</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-dialog { width: 380px; }
.login-err { color: var(--bad); font-size: 12px; margin: -4px 0 0 100px; }
</style>
