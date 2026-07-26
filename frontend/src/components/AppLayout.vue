<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useModelsStore } from '@/stores/models'
import {
  MessageSquare, Database, Activity, Terminal, Settings,
  ChevronLeft, ChevronRight, Brain, Table2, Upload, BarChart3,
  GripVertical,
} from 'lucide-vue-next'
import SessionList from './SessionList.vue'

const router = useRouter()
const route = useRoute()
const modelsStore = useModelsStore()
const collapsed = ref(false)
const sidebarWidth = ref(240)
const dragging = ref(false)

const MIN_WIDTH = 180
const MAX_WIDTH = 420
const STORAGE_KEY = 'sidebar_width'

onMounted(() => {
  modelsStore.fetchModels()
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) sidebarWidth.value = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Number(saved)))
  } catch (_) {}
})

const navItems = [
  { name: 'Chat', key: 'chat', icon: MessageSquare },
  { name: 'Knowledge', key: 'knowledge', icon: Database },
  { name: 'Monitoring', key: 'monitoring', icon: Activity },
  { name: 'Analysis', key: 'analysis', icon: Terminal },
  { name: 'Database', key: 'database', icon: Table2 },
  { name: 'Memories', key: 'memories', icon: Brain },
  { name: 'DataImport', key: 'dataImport', icon: Upload },
  { name: 'ChartStudio', key: 'charts', icon: BarChart3 },
  { name: 'Settings', key: 'settings', icon: Settings },
]

function navigate(name) { router.push({ name }) }

function toggleCollapse() {
  collapsed.value = !collapsed.value
}

function onDragStart(e) {
  dragging.value = true
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

function onDragMove(e) {
  if (!dragging.value) return
  let w = e.clientX
  if (w < MIN_WIDTH) w = MIN_WIDTH
  if (w > MAX_WIDTH) w = MAX_WIDTH
  sidebarWidth.value = w
}

function onDragEnd() {
  if (!dragging.value) return
  dragging.value = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  try { localStorage.setItem(STORAGE_KEY, String(sidebarWidth.value)) } catch (_) {}
}
</script>

<template>
  <div class="app-layout" @mouseup="onDragEnd">
    <aside
      class="sidebar"
      :class="{ collapsed, dragging }"
      :style="{ width: collapsed ? '56px' : sidebarWidth + 'px' }"
    >
      <div class="sidebar-inner">
        <div class="sidebar-header" v-if="!collapsed">
          <h1 class="logo">Research Agent</h1>
        </div>

        <SessionList v-if="!collapsed" />

        <nav class="nav-list">
          <button
            v-for="item in navItems"
            :key="item.name"
            class="nav-item"
            :class="{ active: route.name === item.name }"
            @click="navigate(item.name)"
          >
            <component :is="item.icon" :size="18" />
            <span v-if="!collapsed" class="nav-label">{{ $t('nav.' + item.key) }}</span>
          </button>
        </nav>

        <button class="collapse-btn" @click="toggleCollapse">
          <component :is="collapsed ? ChevronRight : ChevronLeft" :size="16" />
        </button>
      </div>
    </aside>

    <!-- Draggable resize handle -->
    <div
      class="resize-handle"
      :class="{ active: dragging }"
      @mousedown="onDragStart"
    >
      <GripVertical :size="12" />
    </div>

    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-layout { display:flex; height:100vh; overflow:hidden; }
.sidebar {
  background:#1a1a2e; color:#e0e0e0;
  display:flex; flex-direction:column;
  flex-shrink:0; overflow:hidden;
  transition:width 0.2s ease;
}
.sidebar.collapsed { width:56px !important; }
.sidebar.dragging { transition:none !important; }
.sidebar-inner { display:flex; flex-direction:column; height:100%; min-width:0; }
.sidebar-header { padding:20px 16px 12px; border-bottom:1px solid rgba(255,255,255,0.06); }
.logo { font-size:16px; font-weight:700; color:#fff; margin:0; letter-spacing:-0.3px; }
.nav-list { display:flex; flex-direction:column; gap:2px; padding:8px; flex:1; overflow-y:auto; }
.nav-item { display:flex; align-items:center; gap:10px; padding:8px 12px; border:none; border-radius:7px; background:transparent; color:#9ca3af; font-size:13px; cursor:pointer; transition:all 0.12s; text-align:left; width:100%; }
.nav-item:hover { background:rgba(255,255,255,0.06); color:#e0e0e0; }
.nav-item.active { background:rgba(99,102,241,0.15); color:#818cf8; font-weight:500; }
.sidebar.collapsed .nav-item { justify-content:center; padding:9px; }
.collapse-btn { background:none; border:none; color:#6b7280; cursor:pointer; padding:10px; display:flex; align-items:center; justify-content:center; border-top:1px solid rgba(255,255,255,0.06); }
.collapse-btn:hover { color:#e0e0e0; }

/* Resize handle */
.resize-handle {
  width: 8px;
  flex-shrink: 0;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 10;
  color: transparent;
  transition: background 0.12s, color 0.12s;
}
.resize-handle:hover,
.resize-handle.active {
  background: rgba(99, 102, 241, 0.1);
  color: #6366f1;
}
.resize-handle::before {
  content: '';
  position: absolute;
  left: -3px;
  right: -3px;
  top: 0;
  bottom: 0;
}

.main-content { flex:1; background:#f5f5f7; overflow-y:auto; min-width:0; }
</style>