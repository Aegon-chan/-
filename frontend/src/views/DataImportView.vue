<script setup>
import { ref, onMounted } from 'vue'
import { dbApi } from '@/api/database'
import { Upload, Table2, FileSpreadsheet, Database, Loader2, CheckCircle, AlertCircle, RefreshCw } from 'lucide-vue-next'

const step = ref(1)
const importDb = ref('main')
const importTable = ref('')
const tables = ref([])
const selectedFile = ref(null)
const previewResult = ref(null)
const importResult = ref(null)
const previewLoading = ref(false)
const importLoading = ref(false)

// Recent imports
const recentImports = ref([])

onMounted(() => loadTables())

async function loadTables() {
  try {
    const res = await dbApi.tables()
    tables.value = res.tables || []
  } catch (_) {}
}

async function selectFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  selectedFile.value = file
  step.value = 2
  await doPreview(file)
}

async function doPreview(file) {
  if (!file || !importTable.value) return
  previewLoading.value = true
  previewResult.value = null
  importResult.value = null
  try {
    const res = await dbApi.importPreview(importDb.value, importTable.value, file)
    previewResult.value = res
    step.value = 3
  } catch (err) {
    previewResult.value = { error: err.message || 'Preview failed' }
  } finally { previewLoading.value = false }
}

async function doImport() {
  if (!selectedFile.value || !importTable.value) return
  importLoading.value = true
  importResult.value = null
  try {
    const res = await dbApi.importData(importDb.value, importTable.value, selectedFile.value)
    importResult.value = res
  } catch (err) {
    importResult.value = { error: err.message || 'Import failed' }
  } finally { importLoading.value = false }
}

function reset() {
  step.value = 1
  selectedFile.value = null
  previewResult.value = null
  importResult.value = null
}
</script>

<template>
  <div class="import-view">
    <div class="page-header">
      <div><h2>Data Import</h2><p class="page-desc">Upload CSV/XLSX files into database tables</p></div>
    </div>

    <!-- Step 1: Select target -->
    <div class="step-card">
      <div class="step-number">1</div>
      <div class="step-content">
        <h3>Select Target Table</h3>
        <div class="step-controls">
          <select v-model="importDb" class="select" @change="importTable=''">
            <option value="main">Main Database</option>
            <option value="monitoring">Monitoring Database</option>
          </select>
          <select v-model="importTable" class="select">
            <option value="" disabled>Select a table...</option>
            <option v-for="t in tables.filter(t=>t.database===importDb)" :key="t.name" :value="t.name">
              {{ t.name }} ({{ t.row_count }} rows)
            </option>
          </select>
          <button class="btn btn-sm btn-ghost" @click="loadTables"><RefreshCw :size="12" /></button>
        </div>
      </div>
    </div>

    <!-- Step 2: Upload -->
    <div class="step-card" :class="{ dim: importTable.value !== '' }">
      <div class="step-number">2</div>
      <div class="step-content">
        <h3>Upload File</h3>
        <p class="step-desc">Supported: CSV, XLSX, XLS</p>
        <label class="upload-btn" :class="{ disabled: !importTable }">
          <Upload :size="16" /> {{ selectedFile ? selectedFile.name : 'Choose File' }}
          <input type="file" accept=".csv,.xlsx,.xls" hidden :disabled="!importTable" @change="selectFile" />
        </label>
      </div>
    </div>

    <!-- Preview -->
    <div v-if="previewResult" class="step-card">
      <div class="step-number">3</div>
      <div class="step-content">
        <h3>Preview</h3>
        <div v-if="previewLoading" class="load-inline"><Loader2 :size="14" class="spin" /> Previewing...</div>
        <div v-else-if="previewResult.error" class="error-box">{{ previewResult.error }}</div>
        <div v-else>
          <div class="preview-stats">
            <span class="preview-stat">{{ previewResult.total_rows }} rows detected</span>
            <span class="preview-stat">{{ previewResult.estimated_inserts || 0 }} to import</span>
          </div>
          <div v-if="previewResult.column_mapping" class="mapping-box">
            <h4>Column Mapping</h4>
            <div v-for="(dbCol, fileCol) in previewResult.column_mapping" :key="fileCol" class="mapping-row">
              <span class="file-col">{{ fileCol }}</span>
              <span class="arrow">-></span>
              <span class="db-col">{{ dbCol }}</span>
            </div>
          </div>
          <div v-if="previewResult.missing_columns?.length" class="warn-box">
            Unmatched columns: {{ previewResult.missing_columns.join(', ') }}
          </div>
          <div v-if="previewResult.sample_rows?.length" class="sample-box">
            <h4>Sample Data (top 5)</h4>
            <table class="sample-table">
              <thead><tr><th v-for="(v,k) in previewResult.sample_rows[0]" :key="k">{{ k }}</th></tr></thead>
              <tbody><tr v-for="(row,i) in previewResult.sample_rows" :key="i">
                <td v-for="(v,k) in row" :key="k">{{ String(v).slice(0,40) }}</td>
              </tr></tbody>
            </table>
          </div>
          <div class="step-actions">
            <button class="btn btn-primary" :disabled="importLoading" @click="doImport">
              <Loader2 v-if="importLoading" :size="14" class="spin" />
              <Upload v-else :size="14" />
              {{ importLoading ? 'Importing...' : 'Import to Database' }}
            </button>
            <button class="btn btn-ghost" @click="reset">Cancel</button>
          </div>
        </div>
        <!-- Import result -->
        <div v-if="importResult" class="result-box" :class="{ success: importResult.success, error: !importResult.success }">
          <component :is="importResult.success ? CheckCircle : AlertCircle" :size="16" />
          <span>{{ importResult.message || (importResult.success ? 'Import successful' : 'Import failed') }}</span>
          <div v-if="importResult.imported" class="result-detail">{{ importResult.imported }} rows imported, {{ importResult.skipped }} skipped</div>
          <div v-if="importResult.errors?.length" class="result-errors">
            <div v-for="(err, i) in importResult.errors.slice(0,5)" :key="i" class="result-error-item">{{ err.reason }}</div>
          </div>
          <button class="btn btn-sm btn-ghost" @click="reset" style="margin-top:8px">Import Another File</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.import-view { padding: 24px; max-width: 720px; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin:0 0 2px; font-size:20px; color:#111; }
.page-desc { margin:0; color:#666; font-size:13px; }
.btn { display:inline-flex; align-items:center; gap:6px; padding:7px 14px; border-radius:8px; border:none; font-size:13px; cursor:pointer; white-space:nowrap; }
.btn-sm { padding:5px 10px; font-size:12px; }
.btn-ghost { background:#fff; color:#555; border:1px solid #e5e7eb; }
.btn-ghost:hover { background:#f5f5f7; }
.btn-primary { background:#6366f1; color:#fff; }
.btn-primary:hover { background:#4f46e5; }
.btn:disabled { opacity:0.5; cursor:not-allowed; }
.spin { animation:spin 1s linear infinite; }
@keyframes spin { 100% { transform:rotate(360deg); } }
.select { padding:6px 10px; border:1px solid #d1d5db; border-radius:6px; font-size:13px; outline:none; min-width:180px; }
.select:focus { border-color:#6366f1; }
.load-inline { padding:16px 0; color:#999; font-size:13px; display:flex; align-items:center; gap:6px; }

.step-card { display:flex; gap:14px; background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:18px; margin-bottom:14px; }
.step-card.dim { opacity:0.5; }
.step-number { width:28px; height:28px; border-radius:50%; background:#6366f1; color:#fff; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; flex-shrink:0; }
.step-content { flex:1; }
.step-content h3 { margin:0 0 8px; font-size:15px; color:#333; }
.step-desc { margin:0 0 10px; font-size:12px; color:#999; }
.step-controls { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.step-actions { margin-top:14px; display:flex; gap:8px; }
.upload-btn { display:inline-flex; align-items:center; gap:6px; padding:9px 18px; border:1px dashed #d1d5db; border-radius:8px; cursor:pointer; font-size:13px; color:#555; transition:all 0.12s; }
.upload-btn:hover { border-color:#6366f1; color:#6366f1; }
.upload-btn.disabled { opacity:0.4; cursor:not-allowed; }

.error-box { color:#dc2626; font-size:13px; padding:8px 0; }
.preview-stats { display:flex; gap:20px; margin-bottom:12px; }
.preview-stat { font-size:13px; color:#333; font-weight:500; }
.mapping-box { margin-bottom:10px; }
.mapping-box h4 { font-size:12px; color:#555; margin:0 0 6px; }
.mapping-row { display:flex; align-items:center; gap:6px; padding:3px 0; font-size:12px; }
.file-col { font-family:monospace; color:#333; }
.arrow { color:#999; }
.db-col { font-family:monospace; color:#6366f1; }
.warn-box { background:#fef3c7; color:#92400e; padding:8px 12px; border-radius:6px; font-size:12px; margin-bottom:10px; }
.sample-box { margin-bottom:10px; }
.sample-box h4 { font-size:12px; color:#555; margin:0 0 6px; }
.sample-table { width:100%; font-size:11px; border-collapse:collapse; }
.sample-table th { text-align:left; padding:4px 6px; background:#f9fafb; border-bottom:1px solid #e5e7eb; font-weight:600; color:#555; white-space:nowrap; }
.sample-table td { padding:3px 6px; border-bottom:1px solid #f0f0f0; max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.result-box { padding:12px; border-radius:8px; margin-top:10px; font-size:13px; display:flex; flex-direction:column; gap:6px; }
.result-box.success { background:#d1fae5; color:#065f46; }
.result-box.error { background:#fee2e2; color:#991b1b; }
.result-detail { font-size:12px; opacity:0.8; }
.result-errors { font-size:11px; margin-top:4px; }
.result-error-item { color:#dc2626; }
</style>
