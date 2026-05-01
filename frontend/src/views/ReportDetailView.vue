<template>
  <MainLayout>
    <div class="report-detail" v-loading="store.currentLoading">
      <!-- Error state -->
      <div v-if="store.error" class="state-error">
        <el-icon :size="48"><WarningFilled /></el-icon>
        <h2>加载报告失败</h2>
        <p>{{ store.error }}</p>
        <el-button @click="load()">重试</el-button>
      </div>

      <!-- Empty state -->
      <div v-else-if="!store.currentLoading && !store.currentReport" class="state-empty">
        <el-icon :size="48"><Document /></el-icon>
        <h2>未找到报告</h2>
        <el-button @click="$router.push('/reports')">返回报告列表</el-button>
      </div>

      <template v-else-if="store.currentReport">
        <!-- Header -->
        <div class="rd-header">
          <div class="rd-header-left">
            <el-tag :type="typeColor(r.report_type)" size="large">{{ typeLabel(r.report_type) }}</el-tag>
            <h1>{{ r.metadata?.title || r.period_key }}</h1>
            <div class="rd-meta">
              <span v-if="r.metadata?.period_start">
                <el-icon><Calendar /></el-icon>
                {{ r.metadata.period_start }} ~ {{ r.metadata.period_end }}
              </span>
              <span>
                <el-icon><Collection /></el-icon>
                {{ r.metadata?.news_count || 0 }} 条新闻
              </span>
              <span v-if="r.metadata?.generated_at">
                <el-icon><Clock /></el-icon>
                生成于 {{ r.metadata.generated_at?.slice(0, 10) }}
              </span>
            </div>
          </div>
          <div class="rd-header-actions">
            <el-button @click="viewRaw = !viewRaw">
              <el-icon><View /></el-icon>
              {{ viewRaw ? '结构化视图' : '原始Markdown' }}
            </el-button>
            <el-button type="primary" @click="regenerate">
              <el-icon><Refresh /></el-icon>
              重新生成
            </el-button>
            <el-button type="danger" plain @click="confirmDelete">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- Raw Markdown View -->
        <div v-if="viewRaw" class="rd-raw">
          <pre>{{ r.raw_markdown }}</pre>
        </div>

        <!-- Structured View -->
        <div v-else class="rd-structured">
          <!-- Key Findings Hero -->
          <div v-if="r.key_findings" class="key-findings-hero">
            <div class="kf-badge">核心发现</div>
            <p>{{ r.key_findings }}</p>
          </div>

          <!-- Method Note -->
          <div v-if="r.metadata?.method_note" class="method-note">
            <el-icon><InfoFilled /></el-icon>
            {{ r.metadata.method_note }}
          </div>

          <div class="rd-body">
            <!-- Sidebar Nav -->
            <nav class="rd-nav" :class="{ 'is-sticky': navSticky }">
              <div ref="navContainer" class="rd-nav-inner">
                <div class="rd-nav-title">目录</div>
                <a
                  v-for="s in r.sections"
                  :key="s.id"
                  :class="{ active: activeSection === s.id }"
                  @click.prevent="scrollToSection(s.id)"
                >
                  <span class="nav-dot" :class="'dot-' + (s.type || 'text')"></span>
                  {{ s.title }}
                </a>
              </div>
            </nav>

            <!-- Sections -->
            <div class="rd-sections">
              <div
                v-for="s in r.sections"
                :key="s.id"
                :ref="el => sectionRefs[s.id] = el"
                class="report-section"
              >
                <h2 :class="'section-h2 h2-' + s.type">{{ s.title }}</h2>

                <!-- Causal Chain Diagram -->
                <div v-if="s.type === 'causal_chain' && s.items?.length" class="causal-chain">
                  <div v-for="(item, i) in s.items" :key="i" class="cc-node-wrapper">
                    <div class="cc-node" :class="{ cause: item.importance >= 4, effect: item.importance < 4 }">
                      <div class="cc-content">{{ item.content }}</div>
                      <div v-if="item.importance" class="cc-badge">
                        {{ '★'.repeat(Math.min(item.importance, 5)) }}
                      </div>
                    </div>
                    <div v-if="i < s.items.length - 1" class="cc-arrow">
                      <el-icon><Bottom /></el-icon>
                    </div>
                  </div>
                </div>

                <!-- Opportunity Table -->
                <el-table
                  v-else-if="s.type === 'opportunity' && s.items?.length"
                  :data="s.items"
                  style="width:100%"
                  class="opp-table"
                  stripe
                >
                  <el-table-column
                    v-for="col in Object.keys(s.items[0] || {})"
                    :key="col"
                    :prop="col"
                    :label="col"
                    min-width="120"
                  >
                    <template #default="{ row }">
                      <span v-if="col.includes('置信') || col.includes('confid') || col.includes('probability')">
                        <el-tag :type="Number(row[col]) > 0.6 ? 'success' : 'warning'" size="small">
                          {{ row[col] }}{{ Number(row[col]) ? '' : '' }}
                        </el-tag>
                      </span>
                      <span v-else>{{ row[col] }}</span>
                    </template>
                  </el-table-column>
                </el-table>

                <!-- Ranked List -->
                <div v-else-if="(s.type === 'ranked_list' || s.type === 'narrative' || s.type === 'mechanism') && s.items?.length" class="ranked-list">
                  <div v-for="(item, i) in s.items" :key="i" class="rl-item">
                    <div class="rl-rank">{{ i + 1 }}</div>
                    <div class="rl-body">
                      <div class="rl-content">{{ item.content }}</div>
                      <div v-if="item.importance" class="rl-stars">
                        {{ '★'.repeat(Math.min(item.importance, 5)) }}
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Domain Summary / Trend / Insight / Outlook / Text -->
                <div v-else class="section-content">
                  <div v-if="s.content" class="sc-text" v-html="mdToHtml(s.content)"></div>
                  <div v-if="s.items?.length" class="sc-items">
                    <div v-for="(item, i) in s.items" :key="i" class="sc-item">
                      <el-icon><Check /></el-icon>
                      <span>{{ typeof item === 'string' ? item : item.content }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Empty sections -->
              <el-empty v-if="!r.sections?.length" description="无结构化内容" />
            </div>
          </div>
        </div>
      </template>

      <!-- Regenerate Progress Dialog -->
      <el-dialog v-model="progressVisible" title="正在重新生成报告" width="400px" :close-on-click-modal="false" :show-close="false">
        <div class="progress-body">
          <el-progress :percentage="store.taskStatus?.progress || 0" />
          <p class="progress-msg">{{ store.taskStatus?.message }}</p>
        </div>
      </el-dialog>
    </div>
  </MainLayout>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  WarningFilled, Document, View, Refresh, Delete,
  Calendar, Collection, Clock, InfoFilled, Bottom, Check,
} from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useReportsStore } from '@/stores/reports'

const route = useRoute()
const router = useRouter()
const store = useReportsStore()

const viewRaw = ref(false)
const activeSection = ref('')
const navSticky = ref(false)
const navContainer = ref<HTMLElement>()
const sectionRefs: Record<string, HTMLElement | null> = {}
const progressVisible = ref(false)

const r = computed(() => store.currentReport)

function typeLabel(t: string) {
  const m: Record<string, string> = {
    weekly: '周报', monthly: '月报', quarterly: '季报',
    special_city_compare: '城市对比', special_causal_chain: '因果链',
  }
  return m[t] || t
}

function typeColor(t: string) {
  const m: Record<string, string> = {
    weekly: 'primary', monthly: 'success', quarterly: 'warning',
    special_city_compare: 'info', special_causal_chain: 'danger',
  }
  return m[t] || 'info'
}

function mdToHtml(md: string): string {
  if (!md) return ''
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Newlines
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  return '<p>' + html + '</p>'
}

function scrollToSection(id: string) {
  const el = sectionRefs[id]
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    activeSection.value = id
  }
}

let scrollHandler: (() => void) | null = null

function setupScrollSpy() {
  scrollHandler = () => {
    const container = document.querySelector('.app-content')
    if (!container) return
    const scrollTop = container.scrollTop + 120
    let current = ''
    for (const [id, el] of Object.entries(sectionRefs)) {
      if (el && el.offsetTop <= scrollTop) {
        current = id
      }
    }
    if (current) activeSection.value = current
  }
  const container = document.querySelector('.app-content')
  if (container) {
    container.addEventListener('scroll', scrollHandler, { passive: true })
  }
}

function teardownScrollSpy() {
  if (scrollHandler) {
    document.querySelector('.app-content')?.removeEventListener('scroll', scrollHandler)
    scrollHandler = null
  }
}

async function load() {
  const type = route.params.type as string
  const periodKey = route.params.periodKey as string
  if (type && periodKey) {
    await store.fetchReport(type, periodKey)
    await nextTick()
    setupScrollSpy()
  }
}

async function regenerate() {
  if (!r.value) return
  progressVisible.value = true
  await store.generate({
    report_type: r.value.report_type,
    period_key: r.value.period_key,
    force_regenerate: true,
  })
}

async function confirmDelete() {
  if (!r.value) return
  try {
    await ElMessageBox.confirm('永久删除此报告？', '确认', { type: 'warning' })
    await store.deleteReport(r.value.report_type, r.value.period_key)
    ElMessage.success('已删除')
    router.push('/reports')
  } catch {}
}

watch(() => store.taskStatus, (ts) => {
  if (ts && ts.status === 'completed' && ts.result) {
    setTimeout(() => {
      progressVisible.value = false
      load()
    }, 500)
  }
  if (ts && ts.status === 'failed') {
    ElMessage.error(store.generationError || '报告生成失败')
    progressVisible.value = false
  }
})

watch(() => [route.params.type, route.params.periodKey], () => {
  teardownScrollSpy()
  viewRaw.value = false
  load()
})

onMounted(() => load())
onBeforeUnmount(() => teardownScrollSpy())
</script>

<style scoped>
.report-detail {
  max-width: 1200px;
}

/* States */
.state-error, .state-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
  color: var(--text-secondary);
}
.state-error h2, .state-empty h2 {
  margin: 16px 0 8px;
  color: var(--text-primary);
}
.state-error .el-icon { color: var(--color-danger); }
.state-empty .el-icon { color: var(--text-secondary); }

/* Header */
.rd-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  gap: 20px;
}
.rd-header-left h1 {
  font-size: 26px;
  font-weight: 700;
  margin: 12px 0 8px;
}
.rd-meta {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}
.rd-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.rd-header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* Raw Markdown */
.rd-raw {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 24px;
}
.rd-raw pre {
  white-space: pre-wrap;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
}

/* Key Findings Hero */
.key-findings-hero {
  background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(139,92,246,0.08));
  border: 1px solid rgba(59,130,246,0.25);
  border-radius: var(--radius);
  padding: 28px 32px;
  margin-bottom: 24px;
}
.kf-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--color-primary);
  background: rgba(59,130,246,0.15);
  padding: 4px 12px;
  border-radius: 20px;
  margin-bottom: 16px;
}
.key-findings-hero p {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-primary);
}

/* Method Note */
.method-note {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 24px;
  padding: 10px 16px;
  background: var(--bg-card);
  border-left: 3px solid var(--color-warning);
  border-radius: 0 var(--radius) var(--radius) 0;
}

/* Body: Nav + Sections */
.rd-body {
  display: flex;
  gap: 32px;
  align-items: flex-start;
}

/* Section Nav */
.rd-nav {
  width: 220px;
  flex-shrink: 0;
}
.rd-nav.is-sticky .rd-nav-inner {
  position: sticky;
  top: 20px;
}
.rd-nav-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.rd-nav a {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.15s;
  cursor: pointer;
}
.rd-nav a:hover { color: var(--text-primary); background: var(--bg-hover); }
.rd-nav a.active {
  color: var(--color-primary);
  background: rgba(59,130,246,0.1);
}
.nav-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-ranked_list { background: #3b82f6; }
.dot-domain_summary { background: #8b5cf6; }
.dot-trend, .dot-forecast { background: #f59e0b; }
.dot-city_analysis { background: #22c55e; }
.dot-causal_chain { background: #ef4444; }
.dot-opportunity { background: #06b6d4; }
.dot-mechanism { background: #ec4899; }
.dot-narrative { background: #f97316; }
.dot-outlook, .dot-insight { background: #6366f1; }
.dot-text { background: #64748b; }

/* Sections */
.rd-sections {
  flex: 1;
  min-width: 0;
}

.report-section {
  margin-bottom: 36px;
  scroll-margin-top: 20px;
}

.section-h2 {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

/* Causal Chain */
.causal-chain {
  padding: 8px 0;
}
.cc-node-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.cc-node {
  width: 100%;
  max-width: 600px;
  padding: 16px 20px;
  border-radius: var(--radius);
  border: 1px solid var(--border-color);
}
.cc-node.cause {
  background: rgba(239,68,68,0.08);
  border-color: rgba(239,68,68,0.3);
}
.cc-node.effect {
  background: rgba(59,130,246,0.06);
  border-color: rgba(59,130,246,0.25);
}
.cc-content {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
}
.cc-badge {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-warning);
}
.cc-arrow {
  padding: 4px 0;
  color: var(--text-secondary);
}

/* Opportunity Table */
.opp-table {
  border-radius: var(--radius);
}

/* Ranked List */
.ranked-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rl-item {
  display: flex;
  gap: 14px;
  padding: 14px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  transition: border-color 0.15s;
}
.rl-item:hover { border-color: var(--color-primary); }
.rl-rank {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
  background: rgba(59,130,246,0.1);
  border-radius: 6px;
  flex-shrink: 0;
}
.rl-body { flex: 1; min-width: 0; }
.rl-content { font-size: 14px; line-height: 1.5; }
.rl-stars {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-warning);
}

/* Generic Section Content */
.section-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
}
.sc-text :deep(p) { margin-bottom: 10px; }
.sc-text :deep(strong) { color: var(--text-primary); }
.sc-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.sc-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}
.sc-item .el-icon {
  color: var(--color-success);
  flex-shrink: 0;
  margin-top: 3px;
}

/* Progress */
.progress-body { text-align: center; }
.progress-msg { margin-top: 16px; color: var(--text-secondary); font-size: 14px; }

@media (max-width: 768px) {
  .rd-header { flex-direction: column; }
  .rd-header-actions { width: 100%; justify-content: flex-end; flex-wrap: wrap; }
  .rd-body { flex-direction: column; }
  .rd-nav { width: 100%; }
}
</style>
