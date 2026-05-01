import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchDashboardStats } from '@/api/dashboard'
import type { DashboardData } from '@/types'

export const useDashboardStore = defineStore('dashboard', () => {
  const data = ref<DashboardData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastFetch = ref(0)

  const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

  async function fetch(days = 30, force = false) {
    const now = Date.now()
    if (!force && data.value && (now - lastFetch.value) < CACHE_TTL) {
      return data.value
    }
    loading.value = true
    error.value = null
    try {
      data.value = await fetchDashboardStats(days)
      lastFetch.value = now
      return data.value
    } catch (e: any) {
      error.value = e.message || '加载仪表盘失败'
      return null
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, fetch }
})
