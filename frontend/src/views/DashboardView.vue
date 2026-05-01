<template>
  <MainLayout>
    <div class="dashboard" v-loading="store.loading">
      <!-- Stat Cards -->
      <div class="stat-cards">
        <div v-for="s in store.data?.stats" :key="s.label" class="stat-card">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
          <div v-if="s.change" class="stat-change" :class="{ up: s.change.startsWith('+'), down: s.change.startsWith('-') }">
            {{ s.change }}
          </div>
        </div>
      </div>

      <!-- Charts Row 1 -->
      <div class="charts-row">
        <div class="chart-card large">
          <h3>新闻量趋势</h3>
          <div ref="volumeChart" class="chart-box"></div>
        </div>
        <div class="chart-card medium">
          <h3>领域分布</h3>
          <div ref="domainChart" class="chart-box"></div>
        </div>
      </div>

      <!-- Charts Row 2 -->
      <div class="charts-row">
        <div class="chart-card medium">
          <h3>城市分布</h3>
          <div ref="cityChart" class="chart-box"></div>
        </div>
        <div class="chart-card medium">
          <h3>来源统计</h3>
          <div ref="sourceChart" class="chart-box"></div>
        </div>
      </div>

      <!-- Recent Reports -->
      <div class="section">
        <h3>最新报告</h3>
        <div class="report-cards">
          <div
            v-for="r in store.data?.recent_reports"
            :key="r.id"
            class="report-mini-card"
            @click="$router.push(`/reports/${r.report_type}/${r.period_key}`)"
          >
            <div class="rmc-type">{{ typeLabel(r.report_type) }}</div>
            <div class="rmc-period">{{ r.period_key }}</div>
            <div class="rmc-count">{{ r.news_count }} 条新闻</div>
            <div class="rmc-findings">{{ r.key_findings?.slice(0, 120) }}</div>
          </div>
          <el-empty v-if="!store.data?.recent_reports?.length" description="暂无报告" />
        </div>
      </div>
    </div>
  </MainLayout>
</template>

<script setup lang="ts">
import { onMounted, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import MainLayout from '@/layouts/MainLayout.vue'
import { useDashboardStore } from '@/stores/dashboard'

const store = useDashboardStore()
const volumeChart = ref<HTMLDivElement>()
const domainChart = ref<HTMLDivElement>()
const cityChart = ref<HTMLDivElement>()
const sourceChart = ref<HTMLDivElement>()

const CHART_TEXT = '#606266'
const CHART_BORDER = '#e4e7ed'

function typeLabel(t: string) {
  const m: Record<string, string> = {
    weekly: '周报', monthly: '月报', quarterly: '季报',
    special_city_compare: '城市对比', special_causal_chain: '因果链',
  }
  return m[t] || t
}

function renderCharts() {
  const data = store.data
  if (!data) return

  // Volume chart
  if (volumeChart.value) {
    const c = echarts.init(volumeChart.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', data: data.news_by_day.map(d => d.date.slice(5)), axisLabel: { color: CHART_TEXT, fontSize: 10 }, axisLine: { lineStyle: { color: CHART_BORDER } } },
      yAxis: { type: 'value', axisLabel: { color: CHART_TEXT }, splitLine: { lineStyle: { color: CHART_BORDER } } },
      series: [{
        data: data.news_by_day.map(d => d.count),
        type: 'line',
        smooth: true,
        lineStyle: { color: '#3b82f6', width: 2 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{offset: 0, color: 'rgba(59,130,246,0.25)'}, {offset: 1, color: 'rgba(59,130,246,0)'}] } },
        showSymbol: false,
      }],
    })
    setTimeout(() => c.resize(), 100)
  }

  // Domain pie
  if (domainChart.value) {
    const c = echarts.init(domainChart.value)
    c.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['50%', '50%'],
        label: { color: CHART_TEXT, fontSize: 11 },
        data: data.top_domains.map(d => ({ name: d.domain, value: d.count })),
      }],
    })
  }

  // City bar
  if (cityChart.value) {
    const c = echarts.init(cityChart.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 80, right: 20, top: 10, bottom: 20 },
      xAxis: { type: 'value', axisLabel: { color: CHART_TEXT }, splitLine: { lineStyle: { color: CHART_BORDER } } },
      yAxis: { type: 'category', data: data.top_cities.map(d => d.city).reverse(), axisLabel: { color: CHART_TEXT } },
      series: [{
        data: data.top_cities.map(d => d.count).reverse(),
        type: 'bar',
        itemStyle: { color: '#8b5cf6', borderRadius: [0, 4, 4, 0] },
      }],
    })
  }

  // Source bar
  if (sourceChart.value) {
    const c = echarts.init(sourceChart.value)
    c.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 90, right: 20, top: 10, bottom: 20 },
      xAxis: { type: 'value', axisLabel: { color: CHART_TEXT }, splitLine: { lineStyle: { color: CHART_BORDER } } },
      yAxis: { type: 'category', data: data.top_sources.map(d => d.source_name || d.source).reverse(), axisLabel: { color: CHART_TEXT, width: 80, overflow: 'truncate' } },
      series: [{
        data: data.top_sources.map(d => d.count).reverse(),
        type: 'bar',
        itemStyle: { color: '#22c55e', borderRadius: [0, 4, 4, 0] },
      }],
    })
  }
}

onMounted(async () => {
  await store.fetch()
  await nextTick()
  renderCharts()
})

watch(() => store.data, () => nextTick().then(renderCharts))
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 20px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
}

.stat-change {
  font-size: 12px;
  margin-top: 4px;
}

.stat-change.up { color: var(--color-success); }
.stat-change.down { color: var(--color-danger); }

.charts-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.chart-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 20px;
}

.chart-card h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-secondary);
}

.chart-box { height: 260px; }

.section {
  margin-top: 24px;
}

.section h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.report-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.report-mini-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.report-mini-card:hover { border-color: var(--color-primary); }

.rmc-type { font-size: 11px; color: var(--color-primary); text-transform: uppercase; margin-bottom: 4px; }
.rmc-period { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.rmc-count { font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }
.rmc-findings { font-size: 12px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

@media (max-width: 768px) {
  .stat-cards { grid-template-columns: repeat(2, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
}
</style>
