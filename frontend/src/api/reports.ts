import client from './client'
import type { ReportListItem, ReportDetail, GenerateResult, TaskStatus, AvailablePeriod } from '@/types'

export function listReports(params: {
  report_type?: string
  page?: number
  page_size?: number
} = {}): Promise<{ items: ReportListItem[]; total: number; page: number; page_size: number }> {
  return client.get('/reports', { params }).then(r => (r as any).data)
}

export function getReport(type: string, periodKey: string): Promise<ReportDetail> {
  return client.get(`/reports/${type}/${encodeURIComponent(periodKey)}`).then(r => (r as any).data)
}

export function generateReport(data: {
  report_type: string
  period_key?: string
  force_regenerate?: boolean
  topic?: string
  months?: number
  offset?: number
}): Promise<GenerateResult> {
  return client.post('/reports/generate', data).then(r => (r as any).data)
}

export function deleteReport(type: string, periodKey: string): Promise<void> {
  return client.delete(`/reports/${type}/${encodeURIComponent(periodKey)}`).then(r => (r as any).data)
}

export function getTaskStatus(taskId: string): Promise<TaskStatus> {
  return client.get(`/tasks/${taskId}`).then(r => (r as any).data)
}

export function getAvailablePeriods(reportType: string): Promise<AvailablePeriod[]> {
  return client.get(`/meta/available-periods/${reportType}`).then(r => (r as any).data)
}
