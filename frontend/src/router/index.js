import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Chat', component: () => import('@/views/ChatView.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('@/views/KnowledgeView.vue') },
  { path: '/monitoring', name: 'Monitoring', component: () => import('@/views/MonitoringDashboard.vue') },
  { path: '/analysis', name: 'Analysis', component: () => import('@/views/AnalysisView.vue') },
  { path: '/database', name: 'Database', component: () => import('@/views/DatabaseView.vue') },
  { path: '/memories', name: 'Memories', component: () => import('@/views/MemoriesView.vue') },
  { path: '/data-import', name: 'DataImport', component: () => import('@/views/DataImportView.vue') },
  { path: '/chart-studio', name: 'ChartStudio', component: () => import('@/views/ChartStudioView.vue') },
  { path: '/settings', name: 'Settings', component: () => import('@/views/SettingsView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
