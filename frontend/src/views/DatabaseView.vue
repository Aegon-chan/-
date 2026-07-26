<script setup>
import { ref, onMounted, computed } from 'vue'
import { dbApi } from '@/api/database'
import { Database, Table2, Search, Play, Delete, Trash2, Loader2, RefreshCw, ChevronLeft, ChevronRight, Terminal, Upload } from 'lucide-vue-next'

const tables = ref([])
const dbStats = ref([])
const loading = ref(true)

// Browser state
const browserDb = ref('main')
const browserTable = ref('')
const tableColumns = ref([])
const tableRows = ref([])
const totalRows = ref(0)
const currentPage = ref(1)
const pageSize = 50
const searchText = ref('')
const browseLoading = ref(false)
const dbFilter = ref('all')

// SQL query
const querySql = ref('SELECT * FROM sessions LIMIT 10')
const queryDb = ref('main')
const queryResult = ref(null)
const queryLoading = ref(false)

// Batch delete
const deleteIds = ref('')
const deleteLoading = ref(false)

// Condition delete
const dateCol = ref('')
const condAfter = ref('')
const condBefore = ref('')
const condLoading = ref(false)

onMounted(() => { loadTables() })

async function loadTables() {
  loading.value = true
  try {
    const [tblRes, statsRes] = await Promise.all([
      dbApi.tables(),
      dbApi.stats(),
    ])
    tables.value = tblRes.tables || []
    dbStats.value = statsRes.databases || []
  } finally { loading.value = false }
}

const filteredTables = computed(() => {
  if (dbFilter.value === 'all') return tables.value
  return tables.value.filter((t) => t.database === dbFilter.value)
})

function formatRowCount(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : n }

async function browseTable() {
  if (!browserTable.value) return
  browseLoading.value = true
  try {
    const res = await dbApi.browse(browserDb.value, browserTable.value, {
      page: currentPage.value, pageSize, search: searchText.value,
    })
    tableColumns.value = res.columns || []
    tableRows.value = res.rows || []
    totalRows.value = res.total || 0
  } finally { browseLoading.value = false }
}

function selectTable(t) {
  browserDb.value = t.database
  browserTable.value = t.name
  currentPage.value = 1
  searchText.value = ''
  tableColumns.value = t.columns || []
  browseTable()
}

function changePage(delta) {
  currentPage.value = Math.max(1, currentPage.value + delta)
  browseTable()
}

async function runQuery() {
  if (!querySql.value.trim()) return
  queryLoading.value = true
  queryResult.value = null
  try {
    const res = await dbApi.query(querySql.value, queryDb.value)
    queryResult.value = res
  } catch (err) {
    queryResult.value = { error: err.message || 'Query failed' }
  } finally { queryLoading.value = false }
}

async function batchDelete() {
  const ids = deleteIds.value.split(',').map((s) => s.trim()).filter(Boolean)
  if (!ids.length) return
  deleteLoading.value = true
  try {
    await dbApi.batchDelete(browserDb.value, browserTable.value, ids)
    deleteIds.value = ''
    browseTable()
  } catch (err) {
    alert('Delete failed: ' + (err.message || ''))
  } finally { deleteLoading.value = false }
}

async function conditionDelete(dryRun = true) {
  const cond = {}
  if (dateCol.value) {
    const dc = { column: dateCol.value }
    if (condAfter.value) dc.start = condAfter.value
    if (condBefore.value) dc.before = condBefore.value
    if (dc.start || dc.before) cond.date_condition = dc
  }
  if (!cond.date_condition) { alert('Set at least one date condition'); return }
  cond.dry_run = dryRun
  condLoading.value = true
  try {
    await dbApi.deleteByCondition(browserDb.value, browserTable.value, cond)
    if (!dryRun) browseTable()
  } finally { condLoading.value = false }
}

function formatCell(v) {
  if (v === null || v === undefined) return '-'
  const s = String(v)
  return s.length > 80 ? s.slice(0, 80) + '...' : s
}
</script>

<template>
  <div class="db-view">
    <div class="page-header">
      <div><h2>Database Manager</h2><p class="page-desc">Browse, query, and manage database tables</p></div>
      <button class="btn btn-ghost" @click="loadTables"><RefreshCw :size="14" /> Refresh</button>
    </div>

    <!-- Stats -->
    <div v-if="!loading" class="stats-row">
      <div v-for="s in dbStats" :key="s.database" class="stat-card">
        <div class="stat-name">{{ s.database === 'main' ? ($t('database.main') + ' DB') : ($t('database.monitoring') + ' DB') }}</div>
        <div class="stat-vals"><span class="stat-num">{{ s.table_count }}</span> tables</div>
        <div class="stat-sub">{{ s.total_rows }} rows / {{ s.file_size_mb }} MB</div>
      </div>
    </div>

    <div class="db-body">
      <!-- LEFT: Table list -->
      <div class="panel list-panel">
        <div class="panel-head"><Database :size="16" /> Tables <span class="badge">{{ tables.length }}</span></div>
        <div class="filter-row">
          <button v-for="f in [{l:'All',v:'all'},{l:'Main',v:'main'},{l:'Monitoring',v:'monitoring'}]" :key="f.v"
            class="filter-btn" :class="{active:dbFilter===f.v}" @click="dbFilter=f.v">{{ f.l }}</button>
        </div>
        <div class="panel-body">
          <div v-if="loading" class="load-inline"><Loader2 :size="14" class="spin" /></div>
          <div v-for="t in filteredTables" :key="t.database + t.name" class="table-row"
            :class="{active: browserTable===t.name && browserDb===t.database}" @click="selectTable(t)">
            <span class="db-badge" :class="t.database">{{ t.database === 'main' ? 'M' : 'MON' }}</span>
            <span class="tbl-name">{{ t.name }}</span>
            <span class="tbl-rows">{{ formatRowCount(t.row_count) }}</span>
          </div>
        </div>
      </div>

      <!-- RIGHT: Browser + Query -->
      <div class="right-panel">
        <!-- Table Browser -->
        <div class="panel">
          <div class="panel-head"><Table2 :size="16" /> {{ browserTable || 'Select a table' }}
            <span v-if="totalRows" class="badge">{{ totalRows }} rows</span>
          </div>
          <div class="browser-toolbar">
            <div class="search-box"><Search :size="14" /><input v-model="searchText" placeholder="Search..."
              @keydown.enter="browseTable" /></div>
            <button class="btn btn-sm" @click="searchText='';browseTable()">Clear</button>
          </div>
          <div class="panel-body browser-body">
            <div v-if="browseLoading" class="load-inline"><Loader2 :size="14" class="spin" /> Loading...</div>
            <div v-else-if="!tableRows.length" class="load-inline">No data</div>
            <div v-else class="table-wrap">
              <table class="data-table">
                <thead><tr>
                  <th v-for="c in tableColumns" :key="c.name">{{ c.name }}<span class="col-type">{{ c.type }}</span></th>
                  <th class="th-action">Action</th>
                </tr></thead>
                <tbody>
                  <tr v-for="(r, i) in tableRows" :key="i">
                    <td v-for="c in tableColumns" :key="c.name" :title="String(r[c.name] || '')">{{ formatCell(r[c.name]) }}</td>
                    <td><span class="row-action" title="Delete row" @click="console.log('delete',r)"><Trash2 :size="12" /></span></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <!-- Pagination -->
            <div v-if="totalRows > pageSize" class="pagination">
              <button :disabled="currentPage===1" @click="changePage(-1)"><ChevronLeft :size="14" /></button>
              <span>{{ currentPage }} / {{ Math.ceil(totalRows/pageSize) }}</span>
              <button :disabled="currentPage*pageSize>=totalRows" @click="changePage(1)"><ChevronRight :size="14" /></button>
            </div>
          </div>
          <!-- Batch Delete -->
          <div class="panel-footer">
            <div class="del-section">
              <input v-model="deleteIds" placeholder="Enter IDs (comma-separated)" class="input-sm" />
              <button class="btn btn-sm btn-danger" :disabled="!deleteIds.trim()||deleteLoading" @click="batchDelete">
                <Trash2 :size="12" /> Delete
              </button>
            </div>
          </div>
        </div>

        <!-- SQL Query -->
        <div class="panel">
          <div class="panel-head"><Terminal :size="16" /> SQL Query</div>
          <div class="sql-body">
            <div class="sql-controls">
              <select v-model="queryDb" class="select-sm"><option value="main">Main</option><option value="monitoring">Monitoring</option></select>
            </div>
            <textarea v-model="querySql" class="sql-input" rows="3" />
            <button class="btn btn-primary btn-sm" :disabled="queryLoading" @click="runQuery">
              <Play :size="14" /> {{ queryLoading ? 'Running...' : 'Run' }}
            </button>
            <div v-if="queryResult" class="sql-result">
              <div v-if="queryResult.error" class="sql-error">{{ queryResult.error }}</div>
              <div v-else>
                <div class="sql-meta">{{ queryResult.row_count }} rows, {{ queryResult.columns.length }} cols</div>
                <div class="table-wrap" style="max-height:250px"><table class="data-table">
                  <thead><tr><th v-for="c in queryResult.columns" :key="c">{{ c }}</th></tr></thead>
                  <tbody><tr v-for="(r, ri) in queryResult.rows" :key="ri">
                    <td v-for="(c, ci) in queryResult.columns" :key="ci">{{ r[ci] != null ? String(r[ci]).slice(0,60) : '-' }}</td>
                  </tr></tbody>
                </table></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.db-view { padding: 24px; max-width: 1200px; }
.page-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:16px; }
.page-header h2 { margin:0 0 2px; font-size:20px; color:#111; }
.page-desc { margin:0; color:#666; font-size:13px; }
.btn { display:inline-flex; align-items:center; gap:6px; padding:7px 14px; border-radius:8px; border:none; font-size:13px; cursor:pointer; white-space:nowrap; }
.btn-sm { padding:5px 10px; font-size:12px; }
.btn-ghost { background:#fff; color:#555; border:1px solid #e5e7eb; }
.btn-ghost:hover { background:#f5f5f7; }
.btn-primary { background:#6366f1; color:#fff; }
.btn-primary:hover { background:#4f46e5; }
.btn-danger { background:#fee2e2; color:#dc2626; }
.btn-danger:hover:not(:disabled) { background:#fecaca; }
.btn:disabled { opacity:0.5; cursor:not-allowed; }
.spin { animation:spin 1s linear infinite; }
@keyframes spin { 100% { transform:rotate(360deg); } }
.badge { margin-left:auto; font-size:11px; background:#f0f0f0; padding:1px 8px; border-radius:10px; color:#666; font-weight:400; }

.stats-row { display:flex; gap:10px; margin-bottom:16px; }
.stat-card { flex:1; background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:14px 16px; }
.stat-name { font-size:12px; font-weight:600; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.3px; }
.stat-vals { font-size:14px; color:#333; }
.stat-num { font-weight:700; font-size:20px; }
.stat-sub { font-size:11px; color:#999; margin-top:2px; }

.db-body { display:grid; grid-template-columns:280px 1fr; gap:16px; align-items:start; }
.panel { background:#fff; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; margin-bottom:16px; }
.panel-head { display:flex; align-items:center; gap:7px; padding:10px 12px; border-bottom:1px solid #e5e7eb; font-size:13px; font-weight:500; color:#333; }
.panel-body { padding:6px; max-height:480px; overflow-y:auto; }
.panel-footer { padding:8px 12px; border-top:1px solid #e5e7eb; }
.filter-row { display:flex; gap:4px; padding:6px 8px; border-bottom:1px solid #f0f0f0; }
.filter-btn { padding:3px 10px; border-radius:5px; border:none; font-size:11px; cursor:pointer; background:transparent; color:#666; }
.filter-btn.active { background:#6366f1; color:#fff; }
.load-inline { padding:24px; text-align:center; color:#999; font-size:13px; display:flex; align-items:center; justify-content:center; gap:6px; }

.table-row { display:flex; align-items:center; gap:8px; padding:7px 9px; border-radius:6px; cursor:pointer; font-size:12px; transition:all 0.1s; margin-bottom:1px; }
.table-row:hover { background:#f5f5f7; }
.table-row.active { background:rgba(99,102,241,0.08); }
.db-badge { font-size:9px; font-family:'Courier New'; padding:1px 4px; border-radius:3px; flex-shrink:0; }
.db-badge.main { background:#dbeafe; color:#2563eb; }
.db-badge.monitoring { background:#fce7f3; color:#db2777; }
.tbl-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:monospace; }
.tbl-rows { font-size:11px; color:#999; }

.browser-toolbar { display:flex; gap:6px; padding:8px 12px; border-bottom:1px solid #f0f0f0; align-items:center; }
.search-box { flex:1; display:flex; align-items:center; gap:6px; background:#f5f5f7; border-radius:6px; padding:4px 8px; }
.search-box input { border:none; background:transparent; outline:none; font-size:12px; flex:1; }
.browser-body { max-height:350px; }
.table-wrap { overflow-x:auto; }
.data-table { width:100%; font-size:11px; border-collapse:collapse; }
.data-table th { text-align:left; padding:5px 6px; font-weight:600; color:#555; border-bottom:1px solid #e5e7eb; white-space:nowrap; position:sticky; top:0; background:#fff; }
.data-table td { padding:4px 6px; border-bottom:1px solid #f5f5f7; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.data-table tr:hover td { background:#f9fafb; }
.col-type { font-weight:400; color:#999; margin-left:4px; font-size:9px; }
.th-action { width:40px; }
.row-action { cursor:pointer; color:#9ca3af; display:inline-flex; }
.row-action:hover { color:#ef4444; }

.pagination { display:flex; align-items:center; justify-content:center; gap:10px; padding:8px; font-size:12px; color:#666; }
.pagination button { background:none; border:1px solid #e5e7eb; border-radius:5px; padding:4px; cursor:pointer; display:flex; }
.pagination button:disabled { opacity:0.3; cursor:default; }
.del-section { display:flex; gap:6px; }
.input-sm { flex:1; padding:5px 8px; border:1px solid #d1d5db; border-radius:5px; font-size:12px; outline:none; }

.sql-body { padding:10px 12px; }
.sql-controls { margin-bottom:6px; }
.select-sm { padding:4px 8px; border:1px solid #d1d5db; border-radius:5px; font-size:12px; outline:none; }
.sql-input { width:100%; padding:8px 10px; border:1px solid #d1d5db; border-radius:6px; font-size:12px; font-family:monospace; resize:vertical; outline:none; box-sizing:border-box; margin-bottom:8px; }
.sql-input:focus { border-color:#6366f1; }
.sql-result { margin-top:10px; border-top:1px solid #e5e7eb; padding-top:10px; }
.sql-meta { font-size:11px; color:#999; margin-bottom:6px; }
.sql-error { color:#dc2626; font-size:12px; }
</style>
