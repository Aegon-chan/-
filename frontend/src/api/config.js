import request from './request'

export const configApi = {
  getApiKeys() {
    return request.get('/config/api-keys')
  },
  updateApiKeys(data) {
    return request.post('/config/api-keys', data)
  },
}
