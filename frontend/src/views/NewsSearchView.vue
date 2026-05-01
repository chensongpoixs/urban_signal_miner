<template>
  <MainLayout>
    <div class="news-page">
      <!-- Filter Sidebar -->
      <aside class="filter-sidebar">
        <div class="filter-section">
          <h3>筛选条件</h3>
          <el-input v-model="store.filters.keyword" placeholder="搜索关键词..." clearable @input="store.debouncedSearch()">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>

        <div class="filter-section">
          <label>领域</label>
          <el-select v-model="store.filters.domain" clearable placeholder="全部" style="width:100%" @change="store.search()">
            <el-option v-for="d in domains" :key="d.name" :label="d.name" :value="d.name" />
          </el-select>
        </div>

        <div class="filter-section">
          <label>城市</label>
          <el-select v-model="store.filters.city" clearable placeholder="全部" style="width:100%" @change="store.search()">
            <el-option v-for="c in cities" :key="c.name" :label="c.name" :value="c.name" />
          </el-select>
        </div>

        <div class="filter-section">
          <label>来源</label>
          <el-select v-model="store.filters.source" clearable placeholder="全部" style="width:100%" @change="store.search()">
            <el-option v-for="s in sources" :key="s.source" :label="s.source_name || s.source" :value="s.source" />
          </el-select>
        </div>

        <div class="filter-section">
          <label>最低重要性</label>
          <el-rate v-model="store.filters.min_importance" :max="5" @change="store.search()" />
        </div>

        <div class="filter-section">
          <label>开始日期</label>
          <el-date-picker v-model="store.filters.date_from" type="date" placeholder="开始" style="width:100%" value-format="YYYY-MM-DD" @change="store.search()" />
        </div>
        <div class="filter-section">
          <label>结束日期</label>
          <el-date-picker v-model="store.filters.date_to" type="date" placeholder="结束" style="width:100%" value-format="YYYY-MM-DD" @change="store.search()" />
        </div>

        <el-button text @click="store.resetFilters()" style="margin-top:8px">重置筛选</el-button>
      </aside>

      <!-- Results -->
      <section class="results-area">
        <div class="results-header">
          <span class="results-count">{{ store.total.toLocaleString() }} 条结果</span>
          <el-select v-model="store.filters.page_size" style="width:100px" @change="store.search()">
            <el-option :value="10" label="10" />
            <el-option :value="20" label="20" />
            <el-option :value="50" label="50" />
          </el-select>
        </div>

        <div v-loading="store.loading" class="results-list">
          <div v-for="item in store.results" :key="item.id" class="news-card" @click="showDetail(item)">
            <div class="nc-header">
              <span class="nc-source">{{ item.source_name || item.source }}</span>
              <span class="nc-importance">
                <el-rate :model-value="item.importance" disabled :max="5" size="small" />
              </span>
            </div>
            <h4 class="nc-title">{{ item.title }}</h4>
            <p class="nc-summary">{{ item.ai_summary }}</p>
            <div class="nc-meta">
              <span>{{ item.date }}</span>
              <span v-if="item.cities?.length">{{ item.cities.join(', ') }}</span>
              <el-tag v-for="t in (item.tags || []).slice(0, 4)" :key="t" size="small" type="info">{{ t }}</el-tag>
            </div>
          </div>
          <el-empty v-if="!store.loading && !store.results.length" description="未找到结果" />
        </div>

        <div class="results-pagination" v-if="store.total > store.filters.page_size">
          <el-pagination
            v-model:current-page="store.filters.page"
            :page-size="store.filters.page_size"
            :total="store.total"
            layout="prev, pager, next"
            background
            @current-change="(p: number) => store.setPage(p)"
          />
        </div>
      </section>

      <!-- Detail Drawer -->
      <el-drawer v-model="drawerVisible" :title="detailItem?.title" size="600px" direction="rtl">
        <template v-if="detailItem">
          <div class="detail-meta">
            <el-tag type="primary">{{ detailItem.source_name || detailItem.source }}</el-tag>
            <span>{{ detailItem.date }}</span>
            <el-rate :model-value="detailItem.importance" disabled :max="5" />
          </div>
          <div class="detail-section">
            <h4>领域</h4>
            <el-tag v-for="d in detailItem.domain" :key="d" style="margin-right:4px">{{ d }}</el-tag>
          </div>
          <div class="detail-section" v-if="detailItem.cities?.length">
            <h4>城市</h4>
            <span>{{ detailItem.cities.join(', ') }}</span>
          </div>
          <div class="detail-section" v-if="detailItem.tags?.length">
            <h4>标签</h4>
            <el-tag v-for="t in detailItem.tags" :key="t" size="small" style="margin: 2px">{{ t }}</el-tag>
          </div>
          <div class="detail-section">
            <h4>摘要</h4>
            <p>{{ detailItem.ai_summary }}</p>
          </div>
          <div class="detail-section" v-if="detailItem.ai_why_matters">
            <h4>重要性说明</h4>
            <p>{{ detailItem.ai_why_matters }}</p>
          </div>
          <div class="detail-section" v-if="detailItem.entities?.length">
            <h4>实体</h4>
            <div v-for="e in detailItem.entities" :key="e.name" class="entity-item">
              <el-tag :type="e.type === 'company' ? 'success' : e.type === 'person' ? 'warning' : 'info'" size="small">
                {{ e.type }}
              </el-tag>
              {{ e.name }}
            </div>
          </div>
          <div class="detail-section">
            <h4>正文内容</h4>
            <div v-if="contentLoading" class="content-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span> 加载中...</span>
            </div>
            <div v-else-if="articleContent" class="article-body">
              <p v-for="(para, i) in articleContent.split('\n').filter(p => p.trim())" :key="i">{{ para }}</p>
            </div>
            <p v-else class="content-empty">未能获取文章正文内容</p>
          </div>
        </template>
      </el-drawer>
    </div>
  </MainLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useNewsStore } from '@/stores/news'
import { fetchMeta, getNewsContent } from '@/api/news'
import { Search, Loading } from '@element-plus/icons-vue'
import type { NewsItem } from '@/types'

const store = useNewsStore()
const domains = ref<any[]>([])
const cities = ref<any[]>([])
const sources = ref<any[]>([])
const drawerVisible = ref(false)
const detailItem = ref<NewsItem | null>(null)
const articleContent = ref<string | null>(null)
const contentLoading = ref(false)

async function showDetail(item: NewsItem) {
  detailItem.value = item
  articleContent.value = null
  contentLoading.value = true
  drawerVisible.value = true
  try {
    const result = await getNewsContent(item.id)
    articleContent.value = result.content || null
  } catch {
    articleContent.value = null
  } finally {
    contentLoading.value = false
  }
}

onMounted(async () => {
  const [d, c, s] = await Promise.all([
    fetchMeta('domains').catch(() => []),
    fetchMeta('cities').catch(() => []),
    fetchMeta('sources').catch(() => []),
  ])
  domains.value = d
  cities.value = c
  sources.value = s
  store.search()
})
</script>

<style scoped>
.news-page {
  display: flex;
  gap: 24px;
  max-width: 1400px;
}

.filter-sidebar {
  width: 260px;
  flex-shrink: 0;
}

.filter-section {
  margin-bottom: 16px;
}

.filter-section h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.filter-section label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.results-area { flex: 1; min-width: 0; }
.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.results-count { font-size: 14px; color: var(--text-secondary); }
.results-list { min-height: 400px; }
.results-pagination { display: flex; justify-content: center; margin-top: 24px; }

.news-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.news-card:hover { border-color: var(--color-primary); }

.nc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.nc-source { font-size: 12px; color: var(--color-primary); font-weight: 500; }
.nc-title { font-size: 15px; font-weight: 600; margin-bottom: 6px; line-height: 1.4; }
.nc-summary { font-size: 13px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 8px; }
.nc-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }

.detail-meta { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.detail-section { margin-bottom: 16px; }
.detail-section h4 { font-size: 13px; font-weight: 600; margin-bottom: 6px; color: var(--text-secondary); text-transform: uppercase; }
.detail-section p { font-size: 14px; line-height: 1.6; }
.entity-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 14px; }

.content-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 16px 0;
}
.article-body {
  max-height: 500px;
  overflow-y: auto;
  padding: 12px 16px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.article-body p {
  margin-bottom: 8px;
}
.article-body p:last-child {
  margin-bottom: 0;
}
.content-empty {
  font-size: 13px;
  color: var(--text-secondary);
  font-style: italic;
}

@media (max-width: 768px) {
  .news-page { flex-direction: column; }
  .filter-sidebar { width: 100%; }
}
</style>
