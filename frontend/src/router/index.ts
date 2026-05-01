import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { title: '仪表盘' },
    },
    {
      path: '/news',
      name: 'news',
      component: () => import('@/views/NewsSearchView.vue'),
      meta: { title: '新闻搜索' },
    },
    {
      path: '/reports',
      name: 'reports',
      component: () => import('@/views/ReportCenterView.vue'),
      meta: { title: '报告中心' },
    },
    {
      path: '/reports/:type/:periodKey',
      name: 'reportDetail',
      component: () => import('@/views/ReportDetailView.vue'),
      meta: { title: '报告详情' },
    },
  ],
})

export default router
