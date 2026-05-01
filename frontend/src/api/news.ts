import client from './client'
import type { NewsItem } from '@/types'

export interface SearchParams {
  keyword?: string
  domain?: string
  city?: string
  source?: string
  min_importance?: number
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface SearchResult {
  items: NewsItem[]
  total: number
  page: number
  page_size: number
}

export function searchNews(params: SearchParams): Promise<SearchResult> {
  return client.get('/news/search', { params }).then(r => (r as any).data)
}

export function getNewsById(id: string): Promise<NewsItem> {
  return client.get(`/news/${id}`).then(r => (r as any).data)
}

export function getNewsContent(id: string): Promise<{ id: string; title: string; content: string; word_count: number }> {
  return client.get(`/news/${encodeURIComponent(id)}/content`).then(r => (r as any).data)
}

export function fetchMeta(field: string): Promise<any[]> {
  return client.get(`/meta/${field}`).then(r => (r as any).data)
}
