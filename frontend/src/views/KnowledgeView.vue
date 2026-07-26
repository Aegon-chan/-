<script setup>
import { ref, onMounted } from 'vue'
import { knowledgeApi } from '@/api/knowledge'
import { Search, Upload, Trash2, FileText, Loader2 } from 'lucide-vue-next'

const documents = ref([])
const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)
const uploading = ref(false)
const loading = ref(false)

onMounted(() => fetchDocuments())

async function fetchDocuments() {
  loading.value = true
  try {
    const res = await knowledgeApi.list()
    documents.value = res.documents || []
  } catch (_) { /* ignore */ }
  finally { loading.value = false }
}

async function handleUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  uploading.value = true
  try {
    await knowledgeApi.upload(file)
    fetchDocuments()
  } catch (_) { /* ignore */ }
  finally { uploading.value = false; e.target.value = '' }
}

async function deleteDoc(docId) {
  await knowledgeApi.delete(docId)
  documents.value = documents.value.filter((d) => d.doc_id !== docId)
}

async function handleSearch() {
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; return }
  searching.value = true
  try {
    const res = await knowledgeApi.search(q)
    searchResults.value = res.results || []
  } finally { searching.value = false }
}
</script>

<template>
  <div class="knowledge-view">
    <div class="page-header">
      <h2>Knowledge Base</h2>
      <p class="page-desc">Upload and search documents (PDF, TXT, MD)</p>
    </div>

    <div class="toolbar">
      <div class="search-bar">
        <Search :size="16" class="search-icon" />
        <input v-model="searchQuery" class="search-input" placeholder="Semantic search..."
          @keydown.enter="handleSearch" />
        <button class="btn btn-primary" @click="handleSearch" :disabled="searching">
          <Loader2 v-if="searching" :size="14" class="spin" /> Search
        </button>
      </div>
      <div class="upload-area">
        <label class="btn btn-upload" :class="{ disabled: uploading }">
          <Upload :size="16" />
          {{ uploading ? 'Uploading...' : 'Upload' }}
          <input type="file" accept=".txt,.md,.pdf" hidden @change="handleUpload" />
        </label>
      </div>
    </div>

    <!-- Search results -->
    <div v-if="searchResults.length > 0" class="search-results">
      <h3 class="section-title">Search Results</h3>
      <div v-for="(r, i) in searchResults" :key="i" class="result-item">
        <div class="result-content">{{ r.content }}</div>
        <div class="result-meta">Score: {{ (1 - (r.distance || 0)).toFixed(3) }}</div>
      </div>
      <button class="btn btn-ghost" @click="searchResults = []">Clear results</button>
    </div>

    <!-- Document list -->
    <div class="doc-section">
      <h3 class="section-title">Documents</h3>
      <div v-if="loading" class="loading"><Loader2 :size="18" class="spin" /> Loading...</div>
      <div v-else-if="documents.length === 0" class="empty-hint">
        <FileText :size="32" />
        <p>No documents yet. Upload a file to get started.</p>
      </div>
      <div v-else class="doc-list">
        <div v-for="doc in documents" :key="doc.doc_id" class="doc-card">
          <div class="doc-info">
            <FileText :size="16" class="doc-icon" />
            <span class="doc-title">{{ doc.filename }}</span>
          </div>
          <button class="btn-icon" @click="deleteDoc(doc.doc_id)" title="Delete">
            <Trash2 :size="14" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-view { padding: 24px; max-width: 880px; }
.page-header h2 { margin: 0 0 2px; font-size: 20px; color: #111; }
.page-desc { margin: 0 0 20px; color: #666; font-size: 13px; }
.toolbar { display: flex; gap: 10px; margin-bottom: 20px; align-items: center; }
.search-bar { flex: 1; display: flex; align-items: center; gap: 8px; background: #fff; border: 1px solid #d1d5db; border-radius: 10px; padding: 4px 10px; }
.search-bar:focus-within { border-color: #6366f1; }
.search-icon { color: #9ca3af; flex-shrink: 0; }
.search-input { flex: 1; border: none; outline: none; padding: 8px 0; font-size: 14px; background: transparent; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; border: none; font-size: 13px; cursor: pointer; white-space: nowrap; }
.btn-primary { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-upload { background: #f0f0f0; color: #333; }
.btn-upload:hover { background: #e5e5e5; }
.btn-upload.disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { background: none; color: #6366f1; padding: 6px 0; }
.btn-ghost:hover { text-decoration: underline; }
.btn-icon { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 6px; border-radius: 6px; display: flex; }
.btn-icon:hover { background: #fee2e2; color: #ef4444; }
.section-title { font-size: 14px; font-weight: 600; color: #333; margin: 0 0 10px; }
.search-results, .doc-section { margin-bottom: 24px; }
.result-item { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 14px; margin-bottom: 6px; }
.result-content { font-size: 13px; color: #333; margin-bottom: 4px; line-height: 1.6; }
.result-meta { font-size: 11px; color: #999; }
.loading { display: flex; align-items: center; gap: 8px; color: #888; font-size: 13px; padding: 20px 0; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }
.empty-hint { text-align: center; padding: 48px 20px; color: #999; }
.empty-hint p { margin: 8px 0 0; font-size: 13px; }
.doc-list { display: flex; flex-direction: column; gap: 4px; }
.doc-card { display: flex; align-items: center; justify-content: space-between; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; }
.doc-info { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.doc-icon { color: #6366f1; flex-shrink: 0; }
.doc-title { font-size: 13px; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
