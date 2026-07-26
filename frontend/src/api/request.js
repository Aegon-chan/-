import axios from 'axios'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || 'Request failed'
    console.error('[API Error]', msg)
    return Promise.reject(error)
  }
)

export default request
