import request from './request'

export const selfGrowthApi = {
  stats(userId = 'default') {
    return request.get('/self-growth/stats', { params: { user_id: userId } })
  },
  runOptimization(userId = 'default') {
    return request.post('/self-growth/run-optimization', null, { params: { user_id: userId } })
  },
  finetuneStatus(userId = 'default') {
    return request.get('/self-growth/finetune/status', { params: { user_id: userId } })
  },
}

export const feedbackApi = {
  history(userId = 'default', limit = 50) {
    return request.get('/feedback/history', { params: { user_id: userId, limit } })
  },
  stats(userId = 'default') {
    return request.get('/feedback/stats', { params: { user_id: userId } })
  },
}
