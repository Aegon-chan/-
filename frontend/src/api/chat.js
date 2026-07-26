import request from './request'

export const chatApi = {
  async send(sessionId, message, modelId = null, attachments = []) {
    return request.post('/chat/completions', {
      session_id: sessionId,
      message,
      model_id: modelId || undefined,
      attachments,
    })
  },

  stream(sessionId, message, modelId = null, attachments = []) {
    const body = { session_id: sessionId, message, attachments }
    if (modelId) body.model_id = modelId
    return fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  uploadFile(file, onProgress) {
    const form = new FormData()
    form.append('file', file)
    return request.post('/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
  },
}
