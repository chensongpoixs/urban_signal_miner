export interface NewsItem {
  id: string
  date: string
  source: string
  source_name: string
  source_url: string
  rank: number
  title: string
  domain: string[]
  cities: string[]
  entities: { name: string; type: string }[]
  tags: string[]
  importance: number
  ai_summary: string
  ai_why_matters: string
  file_path: string
  word_count: number
}

export interface StatCard {
  label: string
  value: string
  change?: string
}

export interface DailyCount {
  date: string
  count: number
  avg_importance: number
}

export interface DomainDist {
  domain: string
  count: number
  percentage: number
}

export interface CityDist {
  city: string
  count: number
  percentage: number
}

export interface SourceDist {
  source: string
  source_name: string
  count: number
  avg_importance?: number
}

export interface ReportPreview {
  id: number
  report_type: string
  period_key: string
  news_count: number
  key_findings: string
  created_at: string
}

export interface DashboardData {
  stats: StatCard[]
  news_by_day: DailyCount[]
  top_domains: DomainDist[]
  top_cities: CityDist[]
  top_sources: SourceDist[]
  importance_distribution: Record<string, number>
  recent_reports: ReportPreview[]
}

export interface ReportSection {
  id: string
  title: string
  type: string
  content?: string
  items?: any[]
}

export interface ReportDetail {
  report_type: string
  period_key: string
  file_path: string
  metadata: {
    title: string
    period_start: string
    period_end: string
    generated_at: string
    news_count: number
    method_note: string
  }
  sections: ReportSection[]
  key_findings: string
  raw_markdown: string
}

export interface ReportListItem {
  id: number
  report_type: string
  period_key: string
  file_path: string
  news_count: number
  key_findings: string
  created_at: string
}

export interface GenerateResult {
  task_id: string
  status: string
  message: string
  result?: {
    report_type: string
    period_key: string
    file_path?: string
    exists?: boolean
  }
}

export interface TaskStatus {
  task_id: string
  status: string
  progress: number
  message: string
  result?: any
  error?: string
}

export interface AvailablePeriod {
  period_key: string
  label: string
  has_report: boolean
}
