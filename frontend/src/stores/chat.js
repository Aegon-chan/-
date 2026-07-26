import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi } from '@/api/chat'
import { useSessionsStore } from './sessions'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const loading = ref(false)
  const streaming = ref(false)
  const pendingAttachments = ref([])
  const uploading = ref(false)

  async function uploadAttachment(file) {
    // Check if already added
    const exists = pendingAttachments.value.find((a) => a.file.name === file.name && a.file.size === file.size)
    if (exists) return

    const entry = { file, status: 'uploading', progress: 0, url: '', filename: file.name, mime_type: file.type || '', size: file.size }
    pendingAttachments.value.push(entry)

    try {
      const res = await chatApi.uploadFile(file, (e) => {
        entry.progress = Math.round((e.loaded / e.total) * 100)
      })
      entry.status = 'ready'
      entry.url = res.url
      entry.mime_type = res.mime_type || file.type
      entry.filename = res.filename || file.name
      entry.size = res.size || file.size
    } catch (err) {
      entry.status = 'error'
      entry.error = err.message
    }
  }

  function removeAttachment(index) {
    pendingAttachments.value.splice(index, 1)
  }

  function clearAttachments() {
    pendingAttachments.value = []
  }

  async function sendMessage(content, sessionId) {
    loading.value = true

    const attachments = pendingAttachments.value
      .filter((a) => a.status === 'ready' && a.url)
      .map((a) => ({ url: a.url, filename: a.filename, mime_type: a.mime_type, size: a.size }))

    messages.value.push({ role: 'user', content, attachments })
    clearAttachments()

    try {
      const res = await chatApi.send(sessionId, content, null, attachments)
      messages.value.push({
        role: 'assistant',
        content: res.content,
        messageId: res.message_id,
      })
    } catch (err) {
      messages.value.push({
        role: 'assistant',
        content: 'Error: ' + (err.message || 'Request failed'),
      })
    } finally {
      loading.value = false
    }
  }

  async function sendMessageStream(content, sessionId) {
    streaming.value = true
    loading.value = true

    const attachments = pendingAttachments.value
      .filter((a) => a.status === 'ready' && a.url)
      .map((a) => ({ url: a.url, filename: a.filename, mime_type: a.mime_type, size: a.size }))

    messages.value.push({ role: 'user', content, attachments })
    clearAttachments()

    const assistantIdx = messages.value.length
    messages.value.push({ role: 'assistant', content: '', streaming: true })

    try {
      const response = await chatApi.stream(sessionId, content, null, attachments)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.event === 'token') {
              messages.value[assistantIdx].content += data.data
              messages.value[assistantIdx] = { ...messages.value[assistantIdx] }
            } else if (data.event === 'done') {
              messages.value[assistantIdx].streaming = false
              messages.value[assistantIdx].messageId = data.message_id
              messages.value[assistantIdx] = { ...messages.value[assistantIdx] }
              const sStore = useSessionsStore()
              sStore.fetchList()
            }
          } catch (_) {}
        }
      }
    } catch (err) {
      messages.value[assistantIdx] = {
        role: 'assistant',
        content: 'Error: ' + (err.message || 'Connection failed'),
      }
    } finally {
      loading.value = false
      streaming.value = false
    }
  }

  function setMessages(msgs) {
    messages.value = msgs.map((m) => ({
      role: m.role,
      content: m.content,
      messageId: m.id,
      attachments: m.attachments || [],
    }))
  }

  function clearMessages() {
    messages.value = []
  }

  return {
    messages, loading, streaming, pendingAttachments, uploading,
    sendMessage, sendMessageStream, setMessages, clearMessages,
    uploadAttachment, removeAttachment, clearAttachments,
  }
})
