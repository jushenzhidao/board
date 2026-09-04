<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import dayjs from 'dayjs'
import { chQuery, saveSettings, settings, UnauthorizedError } from './api/ch.js'
import { listSites, deleteSite, getSite } from './api/sites.js'
import * as sql from './api/sql.js'
import FilterBar from './components/FilterBar.vue'
import KpiCards from './components/KpiCards.vue'
import TrendCharts from './components/TrendCharts.vue'
import DimTable from './components/DimTable.vue'
import ErrorPanel from './components/ErrorPanel.vue'
import HeatMap from './components/HeatMap.vue'
import SiteSwitcher from './components/SiteSwitcher.vue'
import SiteForm from './components/SiteForm.vue'
import LoginDialog from './components/LoginDialog.vue'

const state = reactive({
  t0: Math.floor(Date.now() / 1000) - 7 * 86400,
  t1: Math.floor(Date.now() / 1000),
  channels: [],
  keys: [],
  users: [],
  models: [],
  tokens: [],
  groups: [],
  groupBy: 'channel',
})

const loading = ref(false)
const error = ref(null)
const showSiteForm = ref(false)
const siteFormMode = ref('create')
const siteFormSite = ref(null)
const lastUpdated = ref('')
const showLogin = ref(false)

const data = reactive({
  kpi: null,
  kpiPrev: null,
  trend: [],
  dims: [],
  errDist: [],
  errList: [],
  heat: [],
  options: { channels: [], models: [], users: [], tokens: [], groups: [], keys: [] },
})

// 渠道 id -> 名称（public/channels/<site>.json，由 scripts/sync_channels.py 按站点生成）
const channelMap = ref({})
const channelName = (id) => {
  const n = channelMap.value[Number(id)]
  return n ? `${n}` : null
}

// 多站点：优先从桥接 /sites 实时读取（支持 UI 增删改），失败回退 public/sites.json 静态索引；当前站点存 localStorage
const sites = ref([])
const site = ref('')
async function loadSites() {
  let list = []
  try {
    list = await listSites()
  } catch {
    try {
      const res = await fetch('sites.json')
      if (res.ok) list = (await res.json()).sites || []
    } catch { /* 忽略 */ }
  }
  sites.value = list
  if (!list.length) { site.value = ''; return }
  if (!site.value || !list.some((s) => s.id === site.value)) site.value = list[0].id
}
async function loadChannelMap() {
  channelMap.value = {}
  try {
    const path = site.value ? `channels/${site.value}.json` : 'channels.json'
    const res = await fetch(path)
    if (!res.ok) return
    const j = await res.json()
    const m = {}
    for (const c of j.channels || []) m[c.id] = c.name
    channelMap.value = m
  } catch { /* 缺失时显示原始 ID */ }
}
// 切换站点：持久化选择，重置站点相关筛选（不同站点的渠道/用户/模型等 id 空间不同），重载映射
function switchSite() {
  saveSettings({ site: site.value })
  state.channels = []
  state.keys = []
  state.users = []
  state.models = []
  state.tokens = []
  state.groups = []
  loadChannelMap()
  refresh()
}

// ---------- 站点管理（可视化增删改） ----------
function onAddSite() {
  siteFormMode.value = 'create'
  siteFormSite.value = null
  showSiteForm.value = true
}

async function onEditSite(s) {
  siteFormMode.value = 'edit'
  try {
    siteFormSite.value = (await getSite(s.id)) || s // 拉取脱敏完整配置用于回填
  } catch {
    siteFormSite.value = s
  }
  showSiteForm.value = true
}

async function onDeleteSite(s) {
  if (!window.confirm(`确定删除站点「${s.name}」（${s.id}）？此操作不可撤销。`)) return
  try {
    await deleteSite(s.id)
  } catch (e) {
    error.value = '删除站点失败：' + e.message
    return
  }
  await loadSites()
  if (site.value === s.id) {
    site.value = sites.value[0]?.id || ''
    if (site.value) { loadChannelMap(); refresh() } else { channelMap.value = {} }
  }
}

async function onSiteSaved(id) {
  await loadSites()
  // 新增站点：自动切换过去；编辑：保持当前并刷新
  if (id && site.value !== id && sites.value.some((s) => s.id === id)) site.value = id
  if (!site.value && sites.value.length) site.value = sites.value[0].id
  saveSettings({ site: site.value })
  loadChannelMap()
  refresh()
}

// 时间粒度自动：≤3h 分钟 / ≤3d 小时 / 其余 天
const gran = computed(() => {
  const span = state.t1 - state.t0
  if (span <= 3 * 3600) return 'minute'
  if (span <= 3 * 86400) return 'hour'
  return 'day'
})

let seq = 0
let refreshCtrl = null
let loadingTimer = null

async function refresh() {
  const my = ++seq
  loading.value = true
  error.value = null
  if (refreshCtrl) refreshCtrl.abort()
  refreshCtrl = new AbortController()
  const signal = refreshCtrl.signal
  // 兜底：30s 后若 loading 还属于本次请求，强制关闭（避免 fetch 挂起导致无限转圈）
  if (loadingTimer) clearTimeout(loadingTimer)
  loadingTimer = setTimeout(() => {
    if (my === seq) {
      error.value = '查询超时（30s），请缩小时间范围后重试'
      loading.value = false
      refreshCtrl = null
    }
  }, 30000)

  const span = state.t1 - state.t0
  const prev = { ...state, t0: state.t0 - span, t1: state.t0 }
  try {
    // 分批发查询：vite dev server 代理对突发连接敏感，实测 4+ 并发会有请求排队 30s+。
    // 最大并发控制在 2 个以内，按渲染优先级分批：
    //   第1批：KPI + 趋势（用户最先看）
    //   第2批：环比 KPI + 维度明细
    //   第3批：报错分布 + 报错明细
    //   第4批：热力图
    //   第5批：下拉选项（options -> keys）
    const [kpi, trend] = await Promise.all([
      chQuery(sql.kpiQuery(state), { signal }).then((r) => r[0] || null),
      chQuery(sql.trendQuery(state, gran.value), { signal }),
    ])
    if (my !== seq) return

    const [kpiPrev, dims] = await Promise.all([
      chQuery(sql.kpiQuery(prev), { signal }).then((r) => r[0] || null),
      chQuery(sql.dimQuery(state, state.groupBy), { signal }),
    ])
    if (my !== seq) return

    const [errDist, errList] = await Promise.all([
      chQuery(sql.errDistQuery(state), { signal }),
      chQuery(sql.errListQuery(state), { signal }),
    ])
    if (my !== seq) return

    const heat = await chQuery(sql.heatQuery(state), { signal })
    if (my !== seq) return

    let options = {}
    let keysOpt = {}
    try {
      options = await chQuery(sql.optionsQuery(state.t0, state.t1), { signal }).then((r) => r[0] || {})
      keysOpt = await chQuery(sql.keyOptionsQuery(state.t0, state.t1), { signal }).then((r) => r[0] || {})
    } catch (e) {
      // 下拉选项失败不阻塞核心看板显示
      if (e.name !== 'AbortError') console.warn('下拉选项加载失败：', e.message)
    }

    data.kpi = kpi
    data.kpiPrev = kpiPrev
    data.trend = trend
    data.dims = dims
    data.errDist = errDist
    data.errList = errList
    data.heat = heat
    data.options = {
      channels: (options.channels || []).map(Number).sort((a, b) => a - b),
      models: options.models || [],
      users: options.users || [],
      tokens: options.tokens || [],
      groups: options.groups || [],
      keys: (keysOpt.keys || []).map((k) => (Array.isArray(k) ? k[0] + ':' + k[1] : String(k))),
    }
    lastUpdated.value = dayjs().format('HH:mm:ss')
  } catch (e) {
    if (my === seq) {
      if (e.name === 'AbortError') {
        // 被取消说明已有新请求接管，不覆盖 error/loading
        return
      }
      if (e.name === 'UnauthorizedError') {
        showLogin.value = true
        return
      }
      error.value = e.message
    }
  } finally {
    if (loadingTimer) clearTimeout(loadingTimer)
    if (my === seq) {
      refreshCtrl = null
      loading.value = false
    }
  }
}

// 下钻：点击维度表某行 -> 追加该维度筛选（用整体替换触发响应式，push 不被 watch 捕获）
function onDrill({ groupBy, dim }) {
  const add = (arr, v) => {
    if (!arr.includes(v)) state[groupBy] = [...arr, v]
  }
  if (groupBy === 'channel') add(state.channels, dim)
  else if (groupBy === 'key') {
    const k = Array.isArray(dim) ? dim[0] + ':' + dim[1] : String(dim)
    if (!state.keys.includes(k)) state.keys = [...state.keys, k]
  } else if (groupBy === 'model') add(state.models, dim)
  else if (groupBy === 'user') add(state.users, dim)
  else if (groupBy === 'token') add(state.tokens, dim)
  else if (groupBy === 'group') add(state.groups, dim)
}

// 维度原始值 -> 显示名
function dimLabel(groupBy, dim) {
  if (groupBy === 'channel') return channelName(dim) || 'ID ' + dim
  if (groupBy === 'key') {
    const [c, i] = Array.isArray(dim) ? dim : String(dim).split(',')
    return (channelName(c) || 'ID ' + c) + ' · K' + i
  }
  if (groupBy === 'group') return dim === '' || dim === null ? '(空)' : dim
  return dim || '(空)'
}

// 有数据的渠道（热力图行）
const heatChannels = computed(() => [...new Set(data.heat.map((r) => Number(r.channel_id)))].sort((a, b) => a - b))

// "全部"：按数据实际时间范围设定区间（±60s 余量，避免边界排除）
async function applyAllTime() {
  try {
    const r = (await chQuery(sql.timeRangeQuery()))[0]
    if (r && r.t0 && r.t1) {
      state.t0 = Number(r.t0) - 60
      state.t1 = Number(r.t1) + 60
    }
  } catch (e) {
    error.value = e.message
  }
}

// 防抖监听筛选变化
let timer = null
watch(
  () => ({ ...state }),
  () => {
    clearTimeout(timer)
    timer = setTimeout(refresh, 350)
  },
  { deep: false },
)

// 登录成功：保存令牌到 localStorage，关闭登录框并重载数据
async function onLogin(token) {
  saveSettings({ token })
  showLogin.value = false
  await loadSites()
  if (site.value) saveSettings({ site: site.value })
  await loadChannelMap()
  refresh()
}

function onLoginClose() {
  showLogin.value = false
  error.value = '未通过访问令牌验证，页面无法加载数据。刷新页面可重新登录。'
}

onMounted(async () => {
  site.value = settings.site || ''
  await loadSites()
  if (site.value) saveSettings({ site: site.value })
  await loadChannelMap()
  refresh()
})
</script>

<template>
  <div :class="{ 'loading-mask': loading }">
    <div class="topbar">
      <h1>渠道看板</h1>
      <span class="sub">
        new-api 网关监控 · 最终结果口径（重试排除）
        <template v-if="lastUpdated"> · 更新于 {{ lastUpdated }}</template>
      </span>
      <div class="spacer"></div>
      <SiteSwitcher :sites="sites" :value="site"
        @change="site = $event; switchSite()"
        @add="onAddSite"
        @edit="onEditSite"
        @delete="onDeleteSite" />
      <span v-if="loading"><span class="spin"></span>加载中</span>
    </div>

    <div v-if="error" class="err-banner">
      查询失败：{{ error }}
      <template v-if="error.includes('无法连接')">——请先启动本地桥接 <code>scripts/dev_bridge.py</code>，或检查连接设置</template>
    </div>

    <FilterBar :state="state" :options="data.options" :channel-name="(id) => channelName(id) || 'ID ' + id"
      @refresh="refresh" @all="applyAllTime" />

    <KpiCards :kpi="data.kpi" :kpi-prev="data.kpiPrev" />

    <TrendCharts :trend="data.trend" :gran="gran" />

    <div class="section-title">维度明细</div>
    <DimTable :rows="data.dims" :group-by="state.groupBy" :dim-label="dimLabel" @drill="onDrill" />

    <div class="section-title">报错分析</div>
    <ErrorPanel :dist="data.errDist" :list="data.errList" :channel-name="(id) => channelName(id) || 'ID ' + id" />

    <HeatMap :heat="data.heat" :channels="heatChannels" :channel-name="(id) => channelName(id) || 'ID ' + id" />
  </div>

  <SiteForm v-if="showSiteForm" :mode="siteFormMode" :site="siteFormSite"
    @close="showSiteForm = false" @saved="onSiteSaved" />

  <LoginDialog v-if="showLogin" @success="onLogin" @close="onLoginClose" />
</template>
