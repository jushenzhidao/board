<script setup>
// 站点配置弹窗（新增 / 编辑）
// 密码 write-only：编辑时服务端只返回脱敏（空）密码，留空保存 = 保留原密码
import { reactive, ref, computed } from 'vue'
import { saveSite, testSite, syncSite } from '../api/sites.js'

const props = defineProps({
  mode: { type: String, default: 'create' }, // 'create' | 'edit'
  site: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const isEdit = computed(() => props.mode === 'edit')

const form = reactive({
  id: props.site?.id || '',
  name: props.site?.name || '',
  ch: { host: props.site?.ch?.host || '', port: props.site?.ch?.port || 9000, user: props.site?.ch?.user || '', password: '', database: props.site?.ch?.database || 'new_api_logs' },
  mysql: { host: props.site?.mysql?.host || '', port: props.site?.mysql?.port || 3306, user: props.site?.mysql?.user || '', password: '', database: props.site?.mysql?.database || '' },
})

const chHasPwd = computed(() => !!props.site?.ch?.has_password)
const mysqlHasPwd = computed(() => !!props.site?.mysql?.has_password)

const busy = ref(false)
const saving = ref(false)
const testResult = ref(null)

function buildSite() {
  const chPort = parseInt(form.ch.port, 10)
  const site = {
    id: form.id.trim(),
    name: form.name.trim(),
    ch: {
      host: form.ch.host.trim(),
      port: Number.isFinite(chPort) ? chPort : 9000,
      user: form.ch.user,
      password: form.ch.password,
      database: form.ch.database.trim(),
    },
  }
  // 只要填了 mysql host 就提交 mysql 块
  if (form.mysql.host.trim()) {
    const mPort = parseInt(form.mysql.port, 10)
    site.mysql = {
      host: form.mysql.host.trim(),
      port: Number.isFinite(mPort) ? mPort : 3306,
      user: form.mysql.user,
      password: form.mysql.password,
      database: form.mysql.database.trim(),
    }
  }
  return site
}

async function test() {
  busy.value = true
  testResult.value = null
  try {
    testResult.value = await testSite(buildSite())
  } catch (e) {
    testResult.value = { ch: { ok: false, error: e.message }, mysql: { ok: false, error: '', skipped: true } }
  } finally {
    busy.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const saved = await saveSite(buildSite())
    // 保存后同步渠道映射，让前端立即拿到渠道名；失败不阻塞（仍按保存成功处理）
    try { await syncSite(saved.id) } catch { /* 忽略 */ }
    emit('saved', saved.id)
    emit('close')
  } catch (e) {
    testResult.value = { ch: { ok: false, error: e.message }, mysql: { ok: false, error: '', skipped: true } }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="mask" @click.self="emit('close')">
    <div class="dialog wide">
      <h3>{{ isEdit ? '编辑站点' : '新增站点' }}</h3>

      <div class="row">
        <label>站点名称</label>
        <input type="text" v-model="form.name" placeholder="显示名，如：主站 / 海外站" />
      </div>
      <div class="row">
        <label>站点 ID</label>
        <input type="text" v-model="form.id" :disabled="isEdit" placeholder="英文标识，如：main / site2"
          :title="isEdit ? '站点 ID 作为标识不可修改' : '用于路由与渠道映射文件命名'" />
      </div>

      <div class="fieldset-title">ClickHouse</div>
      <div class="row">
        <label>地址</label>
        <input type="text" v-model="form.ch.host" placeholder="host" />
        <label class="mini">端口</label>
        <input type="text" v-model="form.ch.port" style="width: 80px" placeholder="9000" />
      </div>
      <div class="row">
        <label>用户</label>
        <input type="text" v-model="form.ch.user" placeholder="default" />
      </div>
      <div class="row">
        <label>密码</label>
        <input type="password" v-model="form.ch.password" autocomplete="new-password"
          :placeholder="chHasPwd ? '已保存（留空保持不变）' : '密码'" />
      </div>
      <div class="row">
        <label>数据库</label>
        <input type="text" v-model="form.ch.database" placeholder="new_api_logs" />
      </div>

      <div class="fieldset-title">MySQL（渠道映射，可选）</div>
      <div class="row">
        <label>地址</label>
        <input type="text" v-model="form.mysql.host" placeholder="留空则跳过渠道同步" />
        <label class="mini">端口</label>
        <input type="text" v-model="form.mysql.port" style="width: 80px" placeholder="3306" />
      </div>
      <div class="row">
        <label>用户</label>
        <input type="text" v-model="form.mysql.user" placeholder="root" />
      </div>
      <div class="row">
        <label>密码</label>
        <input type="password" v-model="form.mysql.password" autocomplete="new-password"
          :placeholder="mysqlHasPwd ? '已保存（留空保持不变）' : '密码'" />
      </div>
      <div class="row">
        <label>数据库</label>
        <input type="text" v-model="form.mysql.database" placeholder="oneapi-master" />
      </div>

      <div class="test-box" v-if="testResult">
        <div class="test-line">
          <span>ClickHouse</span>
          <span :class="testResult.ch.ok ? 'ok' : 'bad'">{{ testResult.ch.ok ? '连接成功' : (testResult.ch.error || '失败') }}</span>
        </div>
        <div class="test-line" v-if="testResult.mysql && !testResult.mysql.skipped">
          <span>MySQL</span>
          <span :class="testResult.mysql.ok ? 'ok' : 'bad'">{{ testResult.mysql.ok ? '连接成功' : (testResult.mysql.error || '失败') }}</span>
        </div>
      </div>

      <div class="foot">
        <button type="button" @click="emit('close')">取消</button>
        <button type="button" :disabled="busy" @click="test">{{ busy ? '测试中…' : '测试连接' }}</button>
        <button type="button" class="primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog.wide { width: 480px; max-height: 90vh; overflow: auto; }
.fieldset-title { font-size: 12px; color: var(--text2); font-weight: 600; margin: 14px 0 8px; padding-top: 10px; border-top: 1px dashed var(--border); }
.mini { width: auto; margin-left: 8px; }
.test-box { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-top: 4px; font-size: 13px; }
.test-line { display: flex; justify-content: space-between; padding: 3px 0; }
.test-line .ok { color: var(--good); }
.test-line .bad { color: var(--bad); }
</style>
