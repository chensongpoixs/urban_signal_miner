/**
 * Urban Signal Miner — 前端运行时配置
 *
 * 此文件在 index.html 中通过 <script> 标签加载，早于应用代码执行。
 * npm run build 后，此文件会原样复制到 dist/config.js。
 * 部署时可直接修改 dist/config.js 来切换后端地址，无需重新构建。
 *
 * 开发模式 (npm run dev):
 *   apiBaseUrl 设为空字符串，请求走 Vite proxy → http://localhost:8003
 *
 * 生产模式 (npm run build 后):
 *   修改 apiBaseUrl 为实际后端地址，例如:
 *   apiBaseUrl: "https://your-server.com"
 */
window.__APP_CONFIG__ = {
  /**
   * 后端 API 地址
   * 开发时设为空字符串（走 Vite proxy）
   * 生产部署时设为后端的完整 URL，例如:
   *   "http://192.168.1.100:8000"
   *   "https://api.your-domain.com"
   */
  apiBaseUrl: ""
}
