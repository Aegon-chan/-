import request from './request'

export const analysisApi = {
  tasks(page = 1) {
    return request.get('/analysis/tasks', { params: { page, page_size: 20 } })
  },
  task(taskId) {
    return request.get(`/analysis/tasks/${taskId}`)
  },
  submitQuery(sessionId, dataType, query) {
    return request.post('/analysis/query', null, {
      params: { session_id: sessionId, data_type: dataType, query },
    })
  },
  generateCode(query, dataType = 'gnss', fileId = null) {
    return request.post('/analysis/nl2query/code', { query, data_type: dataType, file_id: fileId })
  },
  execute(query, dataType = 'gnss', fileId = null) {
    return request.post('/analysis/nl2query/execute', { query, data_type: dataType, file_id: fileId })
  },
  files() {
    return request.get('/analysis/nl2query/files')
  },
}
