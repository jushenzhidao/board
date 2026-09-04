// 站点管理 API 客户端（走桥接服务的 /sites 端点）
// 站点配置（含各站点 CH/MySQL 凭据）只存服务端 config/sites.json，
// 浏览器永不接触明文密码：读取时密码脱敏为空，保存时空密码 = 保留原密码。
import { settings, UnauthorizedError } from './ch.js'

const base = () => settings.baseUrl.replace(/\/+$/, '')

async function req(method, path, body) {
  const opts = { method, headers: {} }
  if (settings.token) opts.headers['X-Board-Token'] = settings.token
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch(base() + path, opts)
  } catch (e) {
    throw new Error('无法连接站点管理服务（/ch/sites）：' + e.message)
  }
  const text = await res.text()
  let j = null
  try { j = JSON.parse(text) } catch { /* 非 JSON 错误页 */ }
  if (res.status === 401) throw new UnauthorizedError()
  if (!res.ok) throw new Error((j && j.error) || ('HTTP ' + res.status + ' ' + text.slice(0, 200)))
  return j
}

/** 站点列表（id/name，不含凭据） */
export async function listSites() {
  const j = await req('GET', '/sites')
  return (j && j.sites) || []
}

/** 单站点配置（密码脱敏为空，带 has_password 标记） */
export async function getSite(id) {
  const j = await req('GET', '/sites/' + encodeURIComponent(id))
  return j.site
}

/** 新建/更新站点（空密码字段 = 保留服务端旧密码） */
export async function saveSite(site) {
  const j = await req('POST', '/sites', { site })
  return j.site
}

/** 删除站点 */
export async function deleteSite(id) {
  await req('DELETE', '/sites/' + encodeURIComponent(id))
}

/** 测试站点 CH/MySQL 连通性 */
export async function testSite(site) {
  return await req('POST', '/sites/test', { site })
}

/** 同步该站点的渠道映射（channels/<id>.json） */
export async function syncSite(id) {
  return await req('POST', '/sites/' + encodeURIComponent(id) + '/sync')
}
