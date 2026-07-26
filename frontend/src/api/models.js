import request from './request'

export const modelApi = {
  list() {
    return request.get('/models')
  },
  get(modelId) {
    return request.get(`/models/${modelId}`)
  },
}
