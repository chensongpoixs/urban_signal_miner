import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import { searchNews, type SearchParams, type SearchResult } from '@/api/news'
import type { NewsItem } from '@/types'

export const useNewsStore = defineStore('news', () => {
  const filters = reactive<SearchParams>({
    keyword: '',
    domain: '',
    city: '',
    source: '',
    min_importance: 0,
    date_from: '',
    date_to: '',
    page: 1,
    page_size: 20,
  })

  const results = ref<NewsItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  async function search(immediate = false) {
    loading.value = true
    error.value = null
    try {
      const params = { ...filters }
      // Clear empty strings
      if (!params.keyword) delete params.keyword
      if (!params.domain) delete params.domain
      if (!params.city) delete params.city
      if (!params.source) delete params.source
      if (!params.min_importance) delete params.min_importance
      if (!params.date_from) delete params.date_from
      if (!params.date_to) delete params.date_to

      const data = await searchNews(params)
      results.value = data.items
      total.value = data.total
      filters.page = data.page
      return data
    } catch (e: any) {
      error.value = e.message || '搜索失败'
      return null
    } finally {
      loading.value = false
    }
  }

  function debouncedSearch() {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => search(), 300)
  }

  function setPage(page: number) {
    filters.page = page
    search()
  }

  function resetFilters() {
    filters.keyword = ''
    filters.domain = ''
    filters.city = ''
    filters.source = ''
    filters.min_importance = 0
    filters.date_from = ''
    filters.date_to = ''
    filters.page = 1
    search()
  }

  return { filters, results, total, loading, error, search, debouncedSearch, setPage, resetFilters }
})
