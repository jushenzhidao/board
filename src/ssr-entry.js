// SSR 构建入口（仅供 scripts/ssr_smoke.js 冒烟测试使用）
import { createSSRApp } from 'vue'
import App from './App.vue'

export function createApp() {
  return createSSRApp(App)
}
