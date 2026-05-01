import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/reports'
import type { ReportListItem, ReportDetail, TaskStatus, AvailablePeriod } from '@/types'

export const useReportsStore = defineStore('reports', () => {
  const items = ref<ReportListItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const currentReport = ref<ReportDetail | null>(null)
  const currentLoading = ref(false)

  // Generation state
  const generating = ref(false)
  const taskStatus = ref<TaskStatus | null>(null)
  const generationError = ref<string | null>(null)

  let pollTimer: ReturnType<typeof setInterval> | null = null

  async function fetchList(type?: string, page = 1, pageSize = 20) {
    loading.value = true
    error.value = null
    try {
      const data = await api.listReports({ report_type: type, page, page_size: pageSize })
      items.value = data.items
      total.value = data.total
      return data
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchReport(type: string, periodKey: string) {
    currentLoading.value = true
    currentReport.value = null
    try {
      currentReport.value = await api.getReport(type, periodKey)
      return currentReport.value
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      currentLoading.value = false
    }
  }

  async function generate(params: {
    report_type: string
    period_key?: string
    force_regenerate?: boolean
    topic?: string
    months?: number
    offset?: number
  }) {
    generating.value = true
    generationError.value = null
    try {
      const result = await api.generateReport(params)
      if (result.status === 'completed') {
        generating.value = false
        return result
      }
      // Start polling
      taskStatus.value = {
        task_id: result.task_id,
        status: 'pending',
        progress: 0,
        message: 'Queued...',
      }
      startPolling(result.task_id)
      return result
    } catch (e: any) {
      generationError.value = e.message
      generating.value = false
      return null
    }
  }

  function startPolling(taskId: string) {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(async () => {
      try {
        const status = await api.getTaskStatus(taskId)
        taskStatus.value = status
        if (status.status === 'completed' || status.status === 'failed') {
          stopPolling()
          generating.value = false
          if (status.status === 'failed') {
            generationError.value = status.error || '生成失败'
          }
        }
      } catch {
        stopPolling()
        generating.value = false
        generationError.value = '检查任务状态失败'
      }
    }, 2000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function deleteReport(type: string, periodKey: string) {
    await api.deleteReport(type, periodKey)
    // Refresh list
    await fetchList()
  }

  async function fetchAvailablePeriods(reportType: string): Promise<AvailablePeriod[]> {
    try {
      return await api.getAvailablePeriods(reportType)
    } catch {
      return []
    }
  }

  return {
    items, total, loading, error, fetchList,
    currentReport, currentLoading, fetchReport,
    generating, taskStatus, generationError, generate, stopPolling,
    deleteReport, fetchAvailablePeriods,
  }
})
