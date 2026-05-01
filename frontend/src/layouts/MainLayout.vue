<template>
  <div class="app-layout">
    <aside class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <div class="logo">
          <el-icon :size="24"><DataBoard /></el-icon>
          <span v-show="!sidebarCollapsed" class="logo-text">城市信号挖掘系统</span>
        </div>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="sidebarCollapsed"
        router
        class="sidebar-menu"
        background-color="#ffffff"
        text-color="#606266"
        active-text-color="#3b82f6"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/news">
          <el-icon><Search /></el-icon>
          <span>新闻搜索</span>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><DocumentChecked /></el-icon>
          <span>报告中心</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-footer">
        <div class="footer-actions">
          <el-tooltip content="数据同步" placement="right" :disabled="!sidebarCollapsed">
            <el-button
              :icon="Refresh"
              :loading="syncing"
              text
              size="small"
              @click="triggerSync"
            >
              <span v-show="!sidebarCollapsed">同步</span>
            </el-button>
          </el-tooltip>
          <el-tooltip content="一键流水线" placement="right" :disabled="!sidebarCollapsed">
            <el-button
              :icon="CaretRight"
              :loading="pipelineRunning"
              text
              size="small"
              type="primary"
              @click="triggerPipeline"
            >
              <span v-show="!sidebarCollapsed">流水线</span>
            </el-button>
          </el-tooltip>
        </div>
        <el-button
          :icon="sidebarCollapsed ? Expand : Fold"
          text
          @click="sidebarCollapsed = !sidebarCollapsed"
        />
      </div>

      <!-- Pipeline Progress Dialog -->
      <el-dialog v-model="pipelineDialogVisible" title="流水线运行中" width="520px" :close-on-click-modal="false" :show-close="!pipelineRunning">
        <div class="pipeline-progress">
          <div v-for="(step, i) in pipelineSteps" :key="i" class="pp-step">
            <el-icon :size="18" :class="'pp-icon pp-' + step.status">
              <component :is="step.status === 'ok' ? 'Check' : step.status === 'running' ? 'Loading' : step.status === 'failed' ? 'Close' : 'More'" />
            </el-icon>
            <span class="pp-name" :class="'pp-text-' + step.status">{{ step.name }}</span>
          </div>
        </div>
        <p class="pp-msg">{{ pipelineMessage }}</p>
        <template #footer v-if="!pipelineRunning">
          <el-button @click="pipelineDialogVisible = false">关闭</el-button>
        </template>
      </el-dialog>
    </aside>
    <main class="app-main">
      <header class="app-header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item v-for="(item, i) in breadcrumbs" :key="i" :to="item.to">
            {{ item.label }}
          </el-breadcrumb-item>
        </el-breadcrumb>
        <h1 class="page-title">{{ pageTitle }}</h1>
      </header>
      <div class="app-content">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Expand, Fold, DataBoard, DataAnalysis, Search, DocumentChecked, Refresh, CaretRight } from '@element-plus/icons-vue'
import client from '@/api/client'

const route = useRoute()
const sidebarCollapsed = ref(false)
const syncing = ref(false)

async function triggerSync() {
  syncing.value = true
  try {
    const res: any = await client.post('/sync')
    const data = res.data
    if (data.status === 'ok') {
      ElMessage.success(`同步完成：${data.message}`)
    } else if (data.status === 'skipped') {
      ElMessage.warning(data.message)
    } else {
      ElMessage.error(data.message || '同步失败')
    }
  } catch (e: any) {
    ElMessage.error(e.message || '同步请求失败')
  } finally {
    syncing.value = false
  }
}

// ── Pipeline state ──
const pipelineRunning = ref(false)
const pipelineDialogVisible = ref(false)
const pipelineSteps = ref<{ name: string; status: string }[]>([])
const pipelineMessage = ref('')
let pipelineTimer: ReturnType<typeof setInterval> | null = null

interface PipelineStatus {
  running: boolean
  state: {
    status: string
    step: string
    step_index: number
    total_steps: number
    steps: { name: string; status: string }[]
    message: string
    started_at: string | null
    finished_at: string | null
  }
}

async function triggerPipeline() {
  if (pipelineRunning.value) return
  pipelineRunning.value = true
  try {
    await client.post('/pipeline')
    pipelineDialogVisible.value = true
    ElMessage.info('流水线已启动')
    startPipelinePolling()
  } catch (e: any) {
    ElMessage.error(e.message || '启动流水线失败')
    pipelineRunning.value = false
  }
}

function startPipelinePolling() {
  if (pipelineTimer) clearInterval(pipelineTimer)
  pipelineTimer = setInterval(async () => {
    try {
      const res: any = await client.get('/pipeline/status')
      const data: PipelineStatus = res.data
      pipelineSteps.value = data.state.steps
      pipelineMessage.value = data.state.message
      pipelineRunning.value = data.running

      if (!data.running) {
        clearInterval(pipelineTimer!)
        pipelineTimer = null
        if (data.state.status === 'completed') {
          ElMessage.success(data.state.message || '流水线完成')
        } else if (data.state.status === 'failed') {
          ElMessage.error(data.state.message || '流水线失败')
        }
        // Keep dialog open so user can see results
      }
    } catch {
      clearInterval(pipelineTimer!)
      pipelineTimer = null
      pipelineRunning.value = false
      ElMessage.error('获取流水线状态失败')
    }
  }, 2000)
}

onBeforeUnmount(() => {
  if (pipelineTimer) clearInterval(pipelineTimer)
})

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    dashboard: '仪表盘',
    news: '新闻搜索',
    reports: '报告中心',
    reportDetail: '报告详情',
  }
  return map[route.name as string] || ''
})

const breadcrumbs = computed(() => {
  const items: { label: string; to?: string }[] = [{ label: '首页', to: '/dashboard' }]
  if (route.name === 'dashboard') return items
  if (route.name === 'news') {
    items.push({ label: '新闻搜索' })
  } else if (route.name === 'reports') {
    items.push({ label: '报告中心' })
  } else if (route.name === 'reportDetail') {
    items.push({ label: '报告中心', to: '/reports' })
    items.push({ label: `${route.params.type}/${route.params.periodKey}` })
  }
  return items
})

const activeMenu = computed(() => {
  if (route.name === 'reportDetail') return '/reports'
  return route.path
})
</script>

<style>
:root {
  --bg-primary: #f5f7fa;
  --bg-secondary: #ffffff;
  --bg-sidebar: #ffffff;
  --bg-card: #ffffff;
  --bg-hover: #f0f2f5;
  --border-color: #e4e7ed;
  --text-primary: #303133;
  --text-secondary: #909399;
  --color-primary: #3b82f6;
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --radius: 8px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
}

.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.app-sidebar {
  width: 240px;
  min-height: 100vh;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width 0.2s;
  flex-shrink: 0;
}

.app-sidebar.collapsed {
  width: 64px;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--color-primary);
}

.logo-text {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border-right: none !important;
  padding-top: 8px;
}

.el-menu-item {
  margin: 2px 8px;
  border-radius: var(--radius);
}

.el-menu-item.is-active {
  background: var(--bg-hover) !important;
}

.sidebar-footer {
  padding: 10px 12px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-actions {
  display: flex;
  gap: 2px;
  flex: 1;
  justify-content: center;
}

.sidebar-footer .el-button {
  font-size: 12px;
}

/* Pipeline progress */
.pipeline-progress {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}

.pp-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 6px;
  font-size: 14px;
}

.pp-icon { flex-shrink: 0; }
.pp-pending { color: var(--text-secondary); }
.pp-running { color: var(--color-primary); animation: spin 1s linear infinite; }
.pp-ok { color: var(--color-success); }
.pp-failed { color: var(--color-danger); }

.pp-name { font-weight: 500; }
.pp-text-pending { color: var(--text-secondary); }
.pp-text-running { color: var(--color-primary); }
.pp-text-ok { color: var(--text-primary); }
.pp-text-failed { color: var(--color-danger); }

.pp-msg {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.app-main {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.app-header {
  padding: 20px 32px 0;
  flex-shrink: 0;
}

.app-header .el-breadcrumb {
  margin-bottom: 4px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin: 8px 0 0;
}

.app-content {
  flex: 1;
  padding: 20px 32px 40px;
  overflow-y: auto;
}

/* Element Plus light theme overrides */
.el-breadcrumb__inner,
.el-breadcrumb__inner.is-link {
  color: var(--text-secondary);
  font-weight: 400;
}

.el-menu {
  background: transparent;
}

/* Responsive */
@media (max-width: 768px) {
  .app-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 100;
    height: 100vh;
  }
  .app-sidebar:not(.collapsed) {
    width: 240px;
    box-shadow: 4px 0 20px rgba(0,0,0,0.5);
  }
  .app-sidebar.collapsed {
    width: 0;
    overflow: hidden;
    border-right: none;
  }
  .app-header {
    padding: 16px 16px 0;
    padding-left: 56px;
  }
  .app-content {
    padding: 12px 16px 24px;
  }
  .page-title {
    font-size: 20px;
  }
}

@media (min-width: 769px) and (max-width: 1024px) {
  .app-content {
    padding: 16px 24px 32px;
  }
}
</style>
