import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 前端统一走同源 /ch/，开发环境转发到本地桥接服务（scripts/dev_bridge.py）
      // 生产环境由 nginx 将 /ch/ 反代到 ClickHouse HTTP (8123)
      // 注意必须带尾部斜杠 '/ch/'：vite 代理是前缀匹配，'/ch' 会劫持 /channels/... 等静态资源
      '/ch/': {
        target: 'http://127.0.0.1:8123',
        changeOrigin: false,
        rewrite: (p) => p.replace(/^\/ch/, ''),
      },
    },
  },
})
