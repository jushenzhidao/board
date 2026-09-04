// ClickHouse 查询客户端（兼容 ClickHouse HTTP 接口语义）
// 开发环境: 经 vite proxy /ch -> scripts/dev_bridge.py (HTTP -> native 9000)
// 生产环境: 经 nginx /ch -> ClickHouse 8123 或桥接服务
// 多站点: 当前站点存 localStorage（站点本身的连接配置在服务端 config/sites.json，
//          由桥接服务按请求头 X-Site 路由，浏览器不接触各站点凭据）

const LS_KEY = 'chBoard.settings'

const defaults = {
  // 开发环境直连桥接（127.0.0.1:8123），避免 vite dev server 代理并发连接排队；
  // 生产环境走同源 /ch/，由 nginx 反代。
  baseUrl: import.meta.env.DEV ? 'http://127.0.0.1:8123' : '/ch',
  site: '',        // 当前站点 id（config/sites.json 中的站点 id）
  user: '',        // 可选：直连 CH 时才需要（走桥接时凭据在服务端）
  password: '',
  token: '',       // 访问令牌（服务端 BOARD_TOKEN 启用时必填，随 X-Board-Token 头发出）
}

// 401 未授权：由调用方捕获后弹出登录框
export class UnauthorizedError extends Error {
  constructor() {
    super('访问令牌无效或已过期')
    this.name = 'UnauthorizedError'
  }
}

export const settings = load()

function load() {
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem(LS_KEY) || '{}') }
  } catch {
    return { ...defaults }
  }
}

export function saveSettings(patch) {
  Object.assign(settings, patch)
  localStorage.setItem(LS_KEY, JSON.stringify(settings))
}

/**
 * 执行 SQL，返回 CH FORMAT JSON 的 data 数组（对象数组）
 */
export async function chQuery(sql, { signal } = {}) {
  // 开发环境兜底：如果用户 localStorage 里存的还是旧 '/ch'，自动直连桥接，避免 vite 代理排队
  let baseUrl = settings.baseUrl
  if (import.meta.env.DEV && baseUrl.match(/^\/ch\/?$/)) {
    baseUrl = 'http://127.0.0.1:8123'
  }
  const url = baseUrl.replace(/\/+$/, '') + '/'
  const headers = { 'Content-Type': 'text/plain; charset=utf-8' }
  if (settings.site) headers['X-Site'] = settings.site
  if (settings.token) headers['X-Board-Token'] = settings.token
  if (settings.user || settings.password) {
    headers.Authorization = 'Basic ' + btoa(settings.user + ':' + settings.password)
  }

  // fetch 没有原生超时，用 AbortController 兜底；同时尊重外部 signal
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 25000) // 桥接 30s，前端 25s 先超时
  if (signal) {
    signal.addEventListener('abort', () => ctrl.abort(), { once: true })
  }

  let res
  try {
    res = await fetch(url, { method: 'POST', headers, body: sql + ' FORMAT JSON', signal: ctrl.signal })
  } catch (e) {
    clearTimeout(timer)
    if (e.name === 'AbortError') throw new Error('查询超时（25s）：请缩小时间范围或检查 ClickHouse 代理')
    throw new Error('无法连接 ClickHouse 代理（/ch）：' + e.message)
  }
  clearTimeout(timer)
  const text = await res.text()
  if (res.status === 401) throw new UnauthorizedError()
  if (!res.ok) throw new Error('ClickHouse ' + res.status + ': ' + text.slice(0, 500))
  let j
  try {
    j = JSON.parse(text)
  } catch {
    throw new Error('响应不是合法 JSON：' + text.slice(0, 300))
  }
  return j.data || []
}
