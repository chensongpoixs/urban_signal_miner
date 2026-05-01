import client from './client'
import type { DashboardData } from '@/types'

export function fetchDashboardStats(days = 30): Promise<DashboardData> {
  return client.get('/dashboard/stats', { params: { days } }).then(r => (r as any).data)
}
