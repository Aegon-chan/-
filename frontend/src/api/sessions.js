import request from './request'

export const sessionApi = {
  list(page = 1, pageSize = 50) {
    return request.get('/sessions', { params: { page, page_size: pageSize } })
  },
  get(id) {
    return request.get(`/sessions/${id}`)
  },
  create(title = 'New Session', modelId = 'deepseek-chat') {
    return request.post('/sessions', { title, model_id: modelId, user_id: 'default' })
  },
  update(id, data) {
    return request.patch(`/sessions/${id}`, data)
  },
  delete(id) {
    return request.delete(`/sessions/${id}`)
  },
}
