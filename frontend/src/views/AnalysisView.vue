<script setup>
import { ref, onMounted } from 'vue'
import { analysisApi } from '@/api/analysis'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import { Terminal, Code, Play, History, FileText, Loader2, Send } from 'lucide-vue-next'

const queryText = ref('')
const dataType = ref('gnss')
const loading = ref(false)
const codeOutput = ref('')
const execResult = ref(null)
const showCode = ref(false)

const tasks = ref([])
const tasksLoading = ref(false)

const dataTypes = [
  { id: 'gnss', label: 'GNSS Displacement' },
  { id: 'groundwater', label: 'Groundwater' },
  { id: 'rainfall', label: 'Rainfall' },
  { id: 'pore_pressure', label: 'Pore Pressure' },
  { id: 'insar', label: 'InSAR' },
]

onMounted(() => fetchTasks())

async function fetchTasks() {
  tasksLoading.value = true
  try {
    const res = await analysisApi.tasks()
    tasks.value = res.tasks || []
  } finally { tasksLoading.value = false }
}

async function handleExecute() {
  const q = queryText.value.trim()
  if (!q || loading.value) return
  loading.value = true
  codeOutput.value = ''
  execResult.value = null
  showCode.value = false

  try {
    const res = await analysisApi.execute(q, dataType.value)
    if (res.code) {
      codeOutput.value = res.code
      showCode.value = true
    }
    execResult.value = res
    fetchTasks()
  } catch (err) {
    execResult.value = { success: false, error: err.message || 'Execution failed' }
  } finally { loading.value = false }
}

async function handleGenerateCode() {
  const q = queryText.value.trim()
  if (!q || loading.value) return
  loading.value = true
  codeOutput.value = ''
  execResult.value = null
  showCode.value = true

  try {
    const res = await analysisApi.generateCode(q, dataType.value)
    codeOutput.value = res.code || res.error || 'No code generated'
  } catch (err) {
    codeOutput.value = 'Error: ' + err.message
  } finally { loading.value = false }
}

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="analysis-view">
    <div class="page-header">
      <div>
        <h2>Data Analysis</h2>
        <p class="page-desc">Natural language to code analysis engine</p>
      </div>
    </div>

    <!-- Query Input -->
    <div class="query-card">
      <div class="qc-header">
        <Terminal :size="16" />
        <span>Natural Language Query</span>
      </div>
      <div class="qc-body">
        <div class="qc-controls">
          <select v-model="dataType" class="select">
            <option v-for="t in dataTypes" :key="t.id" :value="t.id">{{ t.label }}</option>
          </select>
        </div>
        <textarea
          v-model="queryText"
          class="query-input"
          placeholder="Example: Show the average groundwater level for each station in the last 30 days"
          rows="3"
        />
        <div class="qc-actions">
          <button class="btn btn-code" @click="handleGenerateCode" :disabled="loading || !queryText.trim()">
            <Code :size="14" />
            Generate Code
          </button>
          <button class="btn btn-execute" @click="handleExecute" :disabled="loading || !queryText.trim()">
            <Loader2 v-if="loading" :size="14" class="spin" />
            <Play v-else :size="14" />
            {{ loading ? 'Executing...' : 'Execute' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Code Output -->
    <div v-if="showCode && codeOutput" class="code-card">
      <div class="code-header">
        <Code :size="16" />
        <span>Generated Python Code</span>
      </div>
      <pre class="code-block"><code>{{ codeOutput }}</code></pre>
    </div>

    <!-- Execution Result -->
    <div v-if="execResult" class="result-card" :class="{ error: !execResult.success }">
      <div class="result-header">
        <Play :size="16" />
        <span>{{ execResult.success ? 'Execution Result' : 'Error' }}</span>
        <span v-if="execResult.from_cache" class="badge-cache">cached</span>
      </div>
      <div class="result-body">
        <div v-if="execResult.success" class="result-success">
          <div v-if="execResult.result?.output" class="result-output">
            <MarkdownRenderer :content="'```\n' + execResult.result.output + '\n```'" />
          </div>
          <div v-if="execResult.result?.figures?.length" class="result-figures">
            <div v-for="(fig, i) in execResult.result.figures" :key="i" class="result-figure">
              <img :src="'data:image/png;base64,' + fig" alt="Figure" />
            </div>
          </div>
          <div v-else-if="!execResult.result?.output" class="result-empty">
            Query executed successfully (no output)
          </div>
        </div>
        <div v-else class="result-error">
          {{ execResult.error || 'An error occurred' }}
        </div>
      </div>
    </div>

    <!-- Recent Tasks -->
    <div class="tasks-card">
      <div class="tasks-header">
        <History :size="16" />
        <span>Recent Analysis Tasks</span>
      </div>
      <div class="tasks-body">
        <div v-if="tasksLoading" class="loading-inline"><Loader2 :size="14" class="spin" /> Loading...</div>
        <div v-else-if="tasks.length === 0" class="loading-inline">No tasks yet</div>
        <div v-for="t in tasks" :key="t.id" class="task-item">
          <div class="task-query">{{ t.query || '(no query)' }}</div>
          <div class="task-meta">
            <span class="task-type">{{ t.data_type }}</span>
            <span class="task-status" :class="t.status">{{ t.status }}</span>
            <span class="task-time">{{ formatTime(t.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analysis-view { padding: 24px; max-width: 880px; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0 0 2px; font-size: 20px; color: #111; }
.page-desc { margin: 0; color: #666; font-size: 13px; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

.query-card, .code-card, .result-card, .tasks-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; margin-bottom: 16px; overflow: hidden;
}
.qc-header, .code-header, .result-header, .tasks-header {
  display: flex; align-items: center; gap: 7px;
  padding: 10px 14px; border-bottom: 1px solid #e5e7eb;
  font-size: 13px; font-weight: 500; color: #333;
}
.qc-body { padding: 14px; }
.qc-controls { margin-bottom: 10px; }
.select {
  padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px;
  font-size: 13px; outline: none; background: #fff;
}
.select:focus { border-color: #6366f1; }
.query-input {
  width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 14px; font-family: inherit; resize: vertical; outline: none;
  box-sizing: border-box; line-height: 1.5;
}
.query-input:focus { border-color: #6366f1; }
.qc-actions { display: flex; gap: 8px; margin-top: 10px; justify-content: flex-end; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; border: none; font-size: 13px; cursor: pointer; white-space: nowrap; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-code { background: #f0f0f0; color: #333; }
.btn-code:hover:not(:disabled) { background: #e5e5e5; }
.btn-execute { background: #6366f1; color: #fff; }
.btn-execute:hover:not(:disabled) { background: #4f46e5; }

.code-block {
  background: #1a1a2e; color: #e0e0e0; padding: 14px; font-size: 13px;
  overflow-x: auto; margin: 0; font-family: 'SFMono-Regular', Consolas, monospace;
  line-height: 1.6; max-height: 400px;
}

.result-card.error { border-color: #fecaca; }
.result-header .badge-cache { margin-left: auto; font-size: 10px; background: #d1fae5; color: #059669; padding: 1px 8px; border-radius: 8px; }
.result-body { padding: 14px; }
.result-success { min-height: 60px; }
.result-output { font-size: 13px; }
.result-figures { margin-top: 10px; }
.result-figure img { max-width: 100%; border-radius: 8px; border: 1px solid #e5e7eb; }
.result-empty { color: #999; font-size: 13px; padding: 20px 0; text-align: center; }
.result-error { color: #dc2626; font-size: 14px; }

.tasks-body { padding: 6px 10px; max-height: 300px; overflow-y: auto; }
.loading-inline { padding: 16px; text-align: center; color: #999; font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 6px; }
.task-item { padding: 8px 6px; border-bottom: 1px solid #f0f0f0; }
.task-item:last-child { border-bottom: none; }
.task-query { font-size: 13px; color: #333; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-meta { display: flex; gap: 8px; align-items: center; }
.task-type { font-size: 11px; color: #6366f1; background: rgba(99,102,241,0.08); padding: 1px 6px; border-radius: 4px; }
.task-status { font-size: 11px; text-transform: capitalize; }
.task-status.pending { color: #f59e0b; }
.task-status.running { color: #3b82f6; }
.task-status.completed { color: #059669; }
.task-status.failed { color: #dc2626; }
.task-time { font-size: 11px; color: #999; margin-left: auto; }
</style>
