import request from './request'

export const knowledgeApi = {
  list() {
    return request.get('/knowledge/documents')
  },
  delete(docId) {
    return request.delete(`/knowledge/documents/${docId}`)
  },
  search(query, topK = 5) {
    return request.post('/knowledge/search', { query, top_k: topK })
  },
  upload(file, onProgress) {
    const form = new FormData()
    form.append('file', file)
    return request.post('/knowledge/documents', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
  },
}
