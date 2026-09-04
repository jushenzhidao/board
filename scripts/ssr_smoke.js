// SSR 冒烟测试：先 vite build --ssr 编译，再在 Node 中真实执行全部组件的渲染路径
// 覆盖浏览器端才会暴露的模板级运行时错误（onMounted/图表绘制/网络请求不在其中）
// 用法：node scripts/ssr_smoke.js   （需在项目根目录）
import { createRequire } from 'module'
import { fileURLToPath, pathToFileURL } from 'url'
import { execFileSync } from 'child_process'
import path from 'path'

const root = path.resolve(fileURLToPath(new URL('..', import.meta.url)))
const require = createRequire(path.join(root, 'package.json'))
const viteBin = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const nodeBin = process.execPath

// 1) SSR 构建
console.log('[1/3] vite build --ssr ...')
execFileSync(nodeBin, [viteBin, 'build', '--ssr', 'src/ssr-entry.js', '--outDir', 'dist-ssr', '--emptyOutDir'], {
  cwd: root, stdio: 'inherit',
})

// 2) Node 里加载 SSR 产物并渲染（子进程隔离，避免 stub 污染）
console.log('[2/3] renderToString ...')
const entry = path.join(root, 'dist-ssr', 'ssr-entry.js')
const render = `
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
const { createApp } = await import(${JSON.stringify(pathToFileURL(entry).href)})
const { renderToString } = await import('vue/server-renderer')
const html = await renderToString(createApp())
const checks = ${JSON.stringify([
  '渠道看板', '请求数', '成功率', 'FRT P95', 'TPS', '平均耗时', '缓存命中率',
  '报错数', '分组依据', '维度明细', '报错分析', '报错分布', '热力图', '选择站点',
  '渠道', 'Key', '用户', '模型', '令牌', '分组',
])}
const missing = checks.filter((c) => !html.includes(c))
console.log('SSR html length: ' + html.length)
if (missing.length) { console.log('MISSING KEYWORDS: ' + missing.join(', ')); process.exit(1) }
console.log('ALL ' + checks.length + ' KEYWORDS OK — 渲染路径无运行时错误')
`
execFileSync(nodeBin, ['--input-type=module', '--eval', render], { cwd: root, stdio: 'inherit' })

console.log('[3/3] SMOKE PASS')
