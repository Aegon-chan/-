<script setup>
import { ref, onMounted, computed } from 'vue'
import { selfGrowthApi, feedbackApi } from '@/api/selfGrowth'
import { Brain, MessageSquare, TrendingUp, Cpu, Loader2, RefreshCw } from 'lucide-vue-next'

const stats = ref(null)
const feedbacks = ref([])
const loading = ref(true)
const optimizing = ref(false)

onMounted(() => loadAll())

async function loadAll() {
  loading.value = true
  try {
    const [s, f] = await Promise.all([
      selfGrowthApi.stats().catch(() => null),
      feedbackApi.history().catch(() => ({ feedback: [] })),
    ])
    stats.value = s
    feedbacks.value = f.feedback || []
  } finally { loading.value = false }
}

async function runOptimization() {
  optimizing.value = true
  try {
    await selfGrowthApi.runOptimization()
    await loadAll()
  } finally { optimizing.value = false }
}

const memoryTypes = computed(() => {
  if (!stats.value?.memory?.by_type) return []
  return Object.entries(stats.value.memory.by_type).map(([k, v]) => ({ type: k, ...v }))
})

const promptVersions = computed(() => {
  if (!stats.value?.prompt_versions) return []
  return Object.entries(stats.value.prompt_versions).map(([k, v]) => ({ task: k, version: v.version || v, score: v.score || '-' }))
})

const typeLabels = { preference: 'Preference', knowledge: 'Knowledge', experience: 'Experience' }
</script>

<template>
  <div class="memories-view">
    <div class="page-header">
      <div><h2>Self-Growth & Memories</h2><p class="page-desc">Memory network, feedback, and optimization status</p></div>
      <button class="btn btn-ghost" @click="loadAll"><RefreshCw :size="14" /> Refresh</button>
    </div>

    <div v-if="loading" class="load-inline"><Loader2 :size="18" class="spin" /> Loading...</div>

    <template v-else>
      <!-- Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <Brain :size="18" class="sc-icon purple" />
          <div class="sc-body">
            <div class="sc-val">{{ stats?.memory?.total || 0 }}</div>
            <div class="sc-label">Total Memories</div>
          </div>
        </div>
        <div class="stat-card">
          <MessageSquare :size="18" class="sc-icon blue" />
          <div class="sc-body">
            <div class="sc-val">{{ stats?.feedback?.total || 0 }}</div>
            <div class="sc-label">Feedback Given</div>
          </div>
        </div>
        <div class="stat-card">
          <TrendingUp :size="18" class="sc-icon green" />
          <div class="sc-body">
            <div class="sc-val">{{ stats?.optimization_runs || 0 }}</div>
            <div class="sc-label">Optimizations</div>
          </div>
        </div>
        <div class="stat-card">
          <Cpu :size="18" class="sc-icon orange" />
          <div class="sc-body">
            <div class="sc-val">{{ stats?.finetune?.model_count || 0 }}</div>
            <div class="sc-label">Fine-tuned Models</div>
          </div>
        </div>
      </div>

      <!-- Memory Types + Prompt Versions -->
      <div class="detail-grid">
        <div class="panel">
          <div class="panel-head"><Brain :size="16" /> Memory Types</div>
          <div class="panel-body">
            <div v-if="!memoryTypes.length" class="load-inline">No memory data</div>
            <div v-for="m in memoryTypes" :key="m.type" class="memory-row">
              <span class="mem-type">{{ typeLabels[m.type] || m.type }}</span>
              <div class="mem-bar-wrap"><div class="mem-bar" :style="{width: Math.min(100, (m.count||0)*10)+'%'}"></div></div>
              <span class="mem-count">{{ m.count || 0 }}</span>
              <span class="mem-weight">w:{{ (m.avg_weight || 0).toFixed(2) }}</span>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><Cpu :size="16" /> Prompt Versions</div>
          <div class="panel-body">
            <div v-if="!promptVersions.length" class="load-inline">No prompts yet</div>
            <div v-for="p in promptVersions" :key="p.task" class="prompt-row">
              <span class="prompt-task">{{ p.task }}</span>
              <span class="prompt-ver">v{{ p.version }}</span>
              <span class="prompt-score">{{ p.score }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="actions-row">
        <button class="btn btn-primary" :disabled="optimizing" @click="runOptimization">
          <Loader2 v-if="optimizing" :size="14" class="spin" />
          <TrendingUp v-else :size="14" />
          {{ optimizing ? $t('memories.optimizing') : $t('memories.runOptimization') }}
        </button>
      </div>

      <!-- Feedback History -->
      <div class="panel" style="margin-top:16px">
        <div class="panel-head"><MessageSquare :size="16" /> Recent Feedback
          <span class="badge">{{ feedbacks.length }}</span>
        </div>
        <div class="feedback-list">
          <div v-if="!feedbacks.length" class="load-inline">No feedback yet</div>
          <div v-for="(fb, i) in feedbacks" :key="i" class="feedback-item">
            <div class="fb-rating">
              <span v-for="s in 5" :key="s" class="star" :class="{filled: s <= fb.rating}">*</span>
            </div>
            <div class="fb-comment">{{ fb.comment || '(no comment)' }}</div>
            <div class="fb-meta">
              <span>{{ fb.session_id?.slice(0,8) || '' }}</span>
              <span>{{ fb.created_at ? new Date(fb.created_at).toLocaleString('zh-CN') : '' }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.memories-view { padding: 24px; max-width: 960px; }
.page-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:16px; }
.page-header h2 { margin:0 0 2px; font-size:20px; color:#111; }
.page-desc { margin:0; color:#666; font-size:13px; }
.btn { display:inline-flex; align-items:center; gap:6px; padding:7px 14px; border-radius:8px; border:none; font-size:13px; cursor:pointer; white-space:nowrap; }
.btn-ghost { background:#fff; color:#555; border:1px solid #e5e7eb; }
.btn-ghost:hover { background:#f5f5f7; }
.btn-primary { background:#6366f1; color:#fff; }
.btn-primary:hover { background:#4f46e5; }
.btn:disabled { opacity:0.5; cursor:not-allowed; }
.spin { animation:spin 1s linear infinite; }
@keyframes spin { 100% { transform:rotate(360deg); } }
.load-inline { padding:24px; text-align:center; color:#999; font-size:13px; display:flex; align-items:center; justify-content:center; gap:6px; }
.badge { margin-left:auto; font-size:11px; background:#f0f0f0; padding:1px 8px; border-radius:10px; color:#666; font-weight:400; }

.stats-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }
.stat-card { display:flex; align-items:center; gap:12px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px; }
.sc-icon { flex-shrink:0; }
.sc-icon.purple { color:#8b5cf6; } .sc-icon.blue { color:#3b82f6; } .sc-icon.green { color:#10b981; } .sc-icon.orange { color:#f59e0b; }
.sc-body { }
.sc-val { font-size:22px; font-weight:700; color:#111; line-height:1.2; }
.sc-label { font-size:11px; color:#999; margin-top:2px; }

.detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
.panel { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; }
.panel-head { display:flex; align-items:center; gap:7px; padding:10px 12px; border-bottom:1px solid #e5e7eb; font-size:13px; font-weight:500; color:#333; }
.panel-body { padding:8px; }
.memory-row { display:flex; align-items:center; gap:8px; padding:6px 8px; font-size:12px; }
.mem-type { min-width:80px; font-weight:500; color:#333; }
.mem-bar-wrap { flex:1; height:6px; background:#f0f0f0; border-radius:3px; overflow:hidden; }
.mem-bar { height:100%; background:#6366f1; border-radius:3px; }
.mem-count { min-width:30px; text-align:right; color:#555; }
.mem-weight { color:#999; font-size:11px; min-width:40px; text-align:right; }
.prompt-row { display:flex; align-items:center; gap:8px; padding:6px 8px; font-size:12px; }
.prompt-task { flex:1; font-family:monospace; color:#333; }
.prompt-ver { color:#6366f1; font-weight:500; }
.prompt-score { color:#999; font-size:11px; }

.actions-row { margin-bottom:16px; }

.feedback-list { padding:6px; max-height:300px; overflow-y:auto; }
.feedback-item { padding:8px 10px; border-bottom:1px solid #f0f0f0; }
.fb-rating { margin-bottom:4px; }
.star { color:#d1d5db; font-size:14px; }
.star.filled { color:#f59e0b; }
.fb-comment { font-size:12px; color:#333; margin-bottom:4px; }
.fb-meta { display:flex; gap:12px; font-size:11px; color:#999; }
</style>
