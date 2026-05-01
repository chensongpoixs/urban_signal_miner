<template>
  <MainLayout>
    <div class="report-center">
      <div class="rc-header">
        <el-tabs v-model="activeType" @tab-change="onTypeChange">
          <el-tab-pane label="全部" name="" />
          <el-tab-pane label="周报" name="weekly" />
          <el-tab-pane label="月报" name="monthly" />
          <el-tab-pane label="季报" name="quarterly" />
          <el-tab-pane label="城市对比" name="special_city_compare" />
          <el-tab-pane label="因果链" name="special_causal_chain" />
        </el-tabs>
        <el-button type="primary" @click="genDialogVisible = true">
          <el-icon><Plus /></el-icon> 生成报告
        </el-button>
      </div>

      <div v-loading="store.loading" class="rc-grid">
        <div v-for="r in store.items" :key="r.id" class="report-card" @click="$router.push(`/reports/${r.report_type}/${r.period_key}`)">
          <div class="rc-type">
            <el-tag :type="typeColor(r.report_type)" size="small">{{ typeLabel(r.report_type) }}</el-tag>
          </div>
          <div class="rc-period">{{ r.period_key }}</div>
          <div class="rc-news-count">{{ r.news_count }} 条新闻</div>
          <div class="rc-findings">{{ r.key_findings?.slice(0, 200) }}</div>
          <div class="rc-created">{{ r.created_at?.slice(0, 10) }}</div>
          <div class="rc-actions" @click.stop>
            <el-button text size="small" @click="confirmDelete(r)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!store.loading && !store.items.length" description="暂无报告，请生成第一份报告！" />
      </div>

      <!-- Generate Dialog -->
      <el-dialog v-model="genDialogVisible" title="生成报告" width="480px">
        <el-form label-position="top">
          <el-form-item label="报告类型">
            <el-select v-model="genForm.report_type" style="width:100%" @change="onGenTypeChange">
              <el-option v-for="t in reportTypes" :key="t.key" :label="t.label" :value="t.key" />
            </el-select>
          </el-form-item>

          <el-form-item v-if="genForm.report_type === 'special_causal_chain'" label="主题">
            <el-input v-model="genForm.topic" placeholder="例如：AI芯片, 自动驾驶" />
          </el-form-item>

          <el-form-item v-if="genForm.report_type === 'special_city_compare'" label="月份数">
            <el-input-number v-model="genForm.months" :min="1" :max="24" />
          </el-form-item>

          <el-form-item v-if="genForm.report_type === 'quarterly'" label="季度偏移">
            <el-input-number v-model="genForm.offset" :min="-10" :max="0" />
            <span class="hint">0=当前季度, -1=上一季度</span>
          </el-form-item>

          <el-form-item v-if="!['special_causal_chain','special_city_compare'].includes(genForm.report_type)" label="周期">
            <el-select v-model="genForm.period_key" style="width:100%" filterable placeholder="选择周期">
              <el-option v-for="p in availablePeriods" :key="p.period_key" :label="p.label" :value="p.period_key">
                <span>{{ p.label }}</span>
                <el-tag v-if="p.has_report" size="small" type="success" style="margin-left:8px">已有</el-tag>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-checkbox v-model="genForm.force_regenerate">强制重新生成（覆盖已有报告）</el-checkbox>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="genDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="store.generating" @click="doGenerate">生成</el-button>
        </template>
      </el-dialog>

      <!-- Progress Dialog -->
      <el-dialog v-model="progressVisible" title="正在生成报告" width="400px" :close-on-click-modal="false" :show-close="false">
        <div class="progress-body">
          <el-progress :percentage="store.taskStatus?.progress || 0" />
          <p class="progress-msg">{{ store.taskStatus?.message }}</p>
        </div>
      </el-dialog>
    </div>
  </MainLayout>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useReportsStore } from '@/stores/reports'
import type { ReportListItem, AvailablePeriod } from '@/types'

const router = useRouter()
const store = useReportsStore()

const activeType = ref('')
const genDialogVisible = ref(false)
const progressVisible = ref(false)
const availablePeriods = ref<AvailablePeriod[]>([])

const reportTypes = [
  { key: 'weekly', label: '周报' },
  { key: 'monthly', label: '月报' },
  { key: 'quarterly', label: '季度深度分析' },
  { key: 'special_city_compare', label: '城市对比分析' },
  { key: 'special_causal_chain', label: '因果链追踪' },
]

const genForm = reactive({
  report_type: 'weekly',
  period_key: '',
  force_regenerate: false,
  topic: '',
  months: 3,
  offset: 0,
})

function typeLabel(t: string) {
  const m: Record<string, string> = { weekly: '周报', monthly: '月报', quarterly: '季报', special_city_compare: '城市对比', special_causal_chain: '因果链' }
  return m[t] || t
}

function typeColor(t: string) {
  const m: Record<string, string> = { weekly: 'primary', monthly: 'success', quarterly: 'warning', special_city_compare: 'info', special_causal_chain: 'danger' }
  return m[t] || 'info'
}

async function onTypeChange() {
  await store.fetchList(activeType.value || undefined)
}

async function onGenTypeChange() {
  genForm.period_key = ''
  genForm.topic = ''
  if (!['special_causal_chain', 'special_city_compare'].includes(genForm.report_type)) {
    availablePeriods.value = await store.fetchAvailablePeriods(genForm.report_type)
  }
}

async function doGenerate() {
  const params: any = { report_type: genForm.report_type, force_regenerate: genForm.force_regenerate }
  if (genForm.report_type === 'special_causal_chain') {
    params.topic = genForm.topic
    if (!params.topic) { ElMessage.warning('请输入主题'); return }
  } else if (genForm.report_type === 'special_city_compare') {
    params.months = genForm.months
  } else if (genForm.report_type === 'quarterly') {
    params.offset = genForm.offset
  } else {
    params.period_key = genForm.period_key
    if (!params.period_key) { ElMessage.warning('请选择周期'); return }
  }
  genDialogVisible.value = false
  progressVisible.value = true
  const result = await store.generate(params)
  if (result?.status === 'completed' && result.result) {
    // Already exists
    router.push(`/reports/${result.result.report_type}/${result.result.period_key}`)
    progressVisible.value = false
  }
}

watch(() => store.taskStatus, (ts) => {
  if (ts && ts.status === 'completed' && ts.result) {
    setTimeout(() => {
      progressVisible.value = false
      router.push(`/reports/${ts.result.report_type}/${ts.result.period_key}`)
      store.fetchList(activeType.value || undefined)
    }, 500)
  }
  if (ts && ts.status === 'failed') {
    ElMessage.error(store.generationError || '生成失败')
    progressVisible.value = false
  }
})

async function confirmDelete(r: ReportListItem) {
  try {
    await ElMessageBox.confirm(`确定删除此报告？`, '确认', { type: 'warning' })
    await store.deleteReport(r.report_type, r.period_key)
    ElMessage.success('报告已删除')
  } catch {}
}

onMounted(() => {
  store.fetchList()
})
</script>

<style scoped>
.report-center { max-width: 1400px; }
.rc-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.rc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; min-height: 400px; }

.report-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 20px;
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
}
.report-card:hover { border-color: var(--color-primary); transform: translateY(-2px); }
.rc-type { margin-bottom: 8px; }
.rc-period { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
.rc-news-count { font-size: 12px; color: var(--text-secondary); margin-bottom: 12px; }
.rc-findings { font-size: 13px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 12px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.rc-created { font-size: 11px; color: var(--text-secondary); }
.rc-actions { position: absolute; top: 12px; right: 12px; }

.progress-body { text-align: center; }
.progress-msg { margin-top: 16px; color: var(--text-secondary); font-size: 14px; }
.hint { font-size: 12px; color: var(--text-secondary); margin-left: 8px; }
</style>
