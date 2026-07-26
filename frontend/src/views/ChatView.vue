<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useSessionsStore } from '@/stores/sessions'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import {
  Send, Paperclip, X, Loader2, FileText, Image as ImageIcon,
  ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown,
} from 'lucide-vue-next'

const chatStore = useChatStore()
const sessionsStore = useSessionsStore()
const inputText = ref('')
const messagesContainer = ref(null)
const fileInput = ref(null)

// Conversation folding state
const collapsedTurns = ref({})

// Group messages into user+assistant turns
const turns = computed(() => {
  const result = []
  let i = 0
  while (i < chatStore.messages.length) {
    const msg = chatStore.messages[i]
    if (msg.role === 'user') {
      const next = chatStore.messages[i + 1]
      if (next && next.role === 'assistant') {
        result.push({ user: msg, assistant: next, index: result.length })
        i += 2
      } else {
        result.push({ user: msg, assistant: null, index: result.length })
        i += 1
      }
    } else {
      // Orphan assistant message (rare)
      result.push({ user: null, assistant: msg, index: result.length })
      i += 1
    }
  }
  return result
})

const totalMessages = computed(() => chatStore.messages.length)
const expandedCount = computed(() => {
  return turns.value.filter((t) => !collapsedTurns.value[t.index]).length
})

const allCollapsed = computed(() => {
  return turns.value.length > 0 && expandedCount.value === 0
})

function toggleTurn(index) {
  collapsedTurns.value = { ...collapsedTurns.value, [index]: !collapsedTurns.value[index] }
}

function collapseAll() {
  const obj = {}
  for (let i = 0; i < turns.value.length; i++) obj[i] = true
  collapsedTurns.value = obj
}

function expandAll() {
  collapsedTurns.value = {}
}

function getTurnPreview(turn) {
  const text = turn.user?.content || turn.assistant?.content || ''
  return text.replace(/\n/g, ' ').slice(0, 60) + (text.length > 60 ? '...' : '')
}

// --- Existing functions ---

async function ensureSession() {
  if (!sessionsStore.currentId) {
    await sessionsStore.createSession('New Conversation')
  }
  return sessionsStore.currentId
}

async function handleSubmit() {
  const text = inputText.value.trim()
  if ((!text && chatStore.pendingAttachments.length === 0) || chatStore.loading) return
  inputText.value = ''
  const sessionId = await ensureSession()
  // Auto-expand when new message starts
  expandAll()
  await chatStore.sendMessageStream(text, sessionId)
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  }
}

function openFilePicker() { fileInput.value?.click() }

function handleFileSelect(e) {
  const files = e.target.files
  if (!files?.length) return
  for (const file of files) chatStore.uploadAttachment(file)
  e.target.value = ''
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function isImage(mime) { return mime?.startsWith('image/') }

function attachmentPreviewUrl(att) {
  if (att.url) return att.url
  if (att.file) return URL.createObjectURL(att.file)
  return ''
}

function openUrl(url) { window.open(url, '_blank') }

// Auto-scroll on new turns
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
)
</script>

<template>
  <div class="chat-view">
    <div ref="messagesContainer" class="messages-area">
      <!-- Empty state -->
      <div v-if="turns.length === 0" class="empty-state">
        <div class="empty-icon">AI</div>
        <h2>{{ $t('chat.emptyTitle') }}</h2>
        <p>{{ $t('chat.emptyDesc') }}</p>
        <p class="empty-hint">{{ $t('chat.emptyHint') }}</p>
      </div>

      <div v-else class="messages-list">
        <!-- Global collapse controls -->
        <div class="collapse-controls">
          <button class="collapse-btn" @click="collapseAll" :disabled="allCollapsed" :title="$t('chat.collapseAll')">
            <ChevronsDownUp :size="14" />
          </button>
          <button class="collapse-btn" @click="expandAll" :disabled="!allCollapsed && expandedCount === turns.length" :title="$t('chat.expandAll')">
            <ChevronsUpDown :size="14" />
          </button>
          <span class="collapse-info">{{ expandedCount }} / {{ turns.length }} {{ $t('chat.turns') }}</span>
        </div>

        <!-- Turns -->
        <div
          v-for="turn in turns"
          :key="turn.index"
          class="turn"
          :class="{ collapsed: collapsedTurns[turn.index] }"
        >
          <!-- Turn header (click to toggle) -->
          <div
            class="turn-header"
            @click="toggleTurn(turn.index)"
            :title="collapsedTurns[turn.index] ? 'Click to expand' : 'Click to collapse'"
          >
            <button class="turn-toggle">
              <component :is="collapsedTurns[turn.index] ? ChevronRight : ChevronDown" :size="14" />
            </button>
            <span class="turn-label">{{ turn.user?.content ? 'You' : 'AI' }}</span>
            <span class="turn-preview">{{ getTurnPreview(turn) }}</span>
          </div>

          <!-- Turn body (hidden when collapsed) -->
          <div v-show="!collapsedTurns[turn.index]" class="turn-body">
            <!-- User message -->
            <div v-if="turn.user" class="message user">
              <div class="message-content">
                <div v-if="turn.user.attachments?.length" class="msg-attachments">
                  <div v-for="(att, j) in turn.user.attachments" :key="j" class="msg-att">
                    <img v-if="isImage(att.mime_type) && att.url" :src="att.url" class="msg-img" alt="attachment" @click="openUrl(att.url)" />
                    <div v-else class="msg-file"><FileText :size="14" /><span class="msg-filename">{{ att.filename }}</span></div>
                  </div>
                </div>
                <div v-if="turn.user.content" class="message-bubble user-bubble">{{ turn.user.content }}</div>
              </div>
            </div>

            <!-- Assistant message -->
            <div v-if="turn.assistant" class="message assistant">
              <div class="avatar">AI</div>
              <div class="message-content">
                <div class="message-bubble assistant-bubble">
                  <MarkdownRenderer v-if="turn.assistant.content" :content="turn.assistant.content" />
                  <div v-if="turn.assistant.streaming" class="streaming-indicator">
                    <Loader2 :size="14" class="spin" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Pending attachments -->
    <div v-if="chatStore.pendingAttachments.length" class="pending-attachments">
      <div v-for="(att, i) in chatStore.pendingAttachments" :key="i" class="pending-chip" :class="att.status">
        <img v-if="isImage(att.file?.type) && att.file" :src="attachmentPreviewUrl(att)" class="pending-thumb" />
        <ImageIcon v-else-if="isImage(att.mime_type)" :size="14" />
        <FileText v-else :size="14" />
        <span class="pending-name">{{ att.filename }}</span>
        <span class="pending-size">{{ formatSize(att.size) }}</span>
        <Loader2 v-if="att.status === 'uploading'" :size="12" class="spin" />
        <span v-if="att.status === 'uploading'" class="pending-progress">{{ att.progress }}%</span>
        <button class="pending-remove" @click="chatStore.removeAttachment(i)" title="Remove">
          <X :size="12" />
        </button>
      </div>
    </div>

    <!-- Input -->
    <div class="input-area">
      <input ref="fileInput" type="file" hidden multiple accept="image/*,.pdf,.docx,.txt,.md,.csv,.xlsx" @change="handleFileSelect" />
      <button class="attach-btn" @click="openFilePicker" :title="$t('chat.attach')">
        <Paperclip :size="16" />
      </button>
      <textarea
        v-model="inputText"
        class="input-box"
        :placeholder="$t('chat.placeholder')"
        :disabled="chatStore.loading"
        rows="1"
        @keydown="handleKeydown"
        @input="$event.target.style.height = ''; $event.target.style.height = $event.target.scrollHeight + 'px'"
      />
      <button
        class="send-btn"
        :disabled="chatStore.loading || (!inputText.trim() && chatStore.pendingAttachments.length === 0)"
        @click="handleSubmit"
      >
        <Loader2 v-if="chatStore.loading" :size="16" class="spin" />
        <Send v-else :size="16" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-view { display: flex; flex-direction: column; height: 100%; }
.messages-area { flex: 1; overflow-y: auto; padding: 24px; }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #888; }
.empty-icon { width: 56px; height: 56px; border-radius: 14px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; margin-bottom: 16px; }
.empty-state h2 { margin: 0 0 6px; color: #333; font-size: 18px; font-weight: 600; }
.empty-state p { margin: 0; font-size: 13px; color: #999; }
.empty-hint { margin-top: 8px !important; font-size: 12px !important; color: #bbb !important; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* Collapse controls */
.collapse-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}
.collapse-btn {
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  color: #9ca3af;
  display: flex;
  align-items: center;
  transition: all 0.12s;
}
.collapse-btn:hover:not(:disabled) { color: #6366f1; border-color: #6366f1; }
.collapse-btn:disabled { opacity: 0.3; cursor: default; }
.collapse-info { font-size: 11px; color: #999; margin-left: auto; }

/* Messages list */
.messages-list { display: flex; flex-direction: column; gap: 4px; max-width: 900px; margin: 0 auto; width: 100%; }

/* Turn */
.turn {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
  transition: all 0.15s;
}
.turn:hover { border-color: #d1d5db; }
.turn.collapsed { background: #f9fafb; }

/* Turn header */
.turn-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.1s;
}
.turn-header:hover { background: #f5f5f7; }
.turn-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px;
  color: #9ca3af;
  display: flex;
  flex-shrink: 0;
}
.turn-toggle:hover { color: #6366f1; }
.turn-label {
  font-size: 11px;
  font-weight: 600;
  color: #6366f1;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}
.turn-preview {
  font-size: 12px;
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

/* Turn body */
.turn-body { padding: 4px 12px 12px; }

/* Messages */
.message { display: flex; gap: 10px; }
.message.user { justify-content: flex-end; }
.message.assistant { justify-content: flex-start; margin-top: 8px; }
.avatar { width: 28px; height: 28px; border-radius: 7px; background: #6366f1; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; flex-shrink: 0; margin-top: 2px; }
.message-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.message-bubble { padding: 10px 14px; border-radius: 10px; font-size: 14px; line-height: 1.6; overflow-wrap: break-word; word-break: break-word; min-width: 0; }
.user-bubble { background: #6366f1; color: #fff; border-bottom-right-radius: 4px; }
.assistant-bubble { background: #f5f5f7; color: #333; border: 1px solid #e5e7eb; border-bottom-left-radius: 4px; }
.streaming-indicator { margin-top: 4px; color: #818cf8; }

/* Attachments */
.msg-attachments { display: flex; flex-wrap: wrap; gap: 6px; }
.msg-att { display: flex; }
.msg-img { max-width: 200px; max-height: 150px; border-radius: 6px; border: 1px solid #e5e7eb; cursor: pointer; transition: opacity 0.12s; }
.msg-img:hover { opacity: 0.85; }
.msg-file { display: flex; align-items: center; gap: 6px; background: #f5f5f7; padding: 5px 8px; border-radius: 5px; font-size: 12px; color: #555; }
.msg-filename { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Pending attachment chips */
.pending-attachments { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 16px; background: #f9fafb; border-top: 1px solid #e5e7eb; }
.pending-chip { display: flex; align-items: center; gap: 6px; padding: 5px 8px; border-radius: 6px; font-size: 12px; border: 1px solid #e5e7eb; background: #fff; }
.pending-chip.uploading { border-color: #bfdbfe; background: #eff6ff; }
.pending-chip.error { border-color: #fecaca; background: #fef2f2; }
.pending-thumb { width: 28px; height: 28px; border-radius: 4px; object-fit: cover; }
.pending-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #333; }
.pending-size { color: #999; font-size: 11px; }
.pending-progress { color: #6366f1; font-size: 11px; font-weight: 500; }
.pending-remove { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 1px; display: flex; border-radius: 3px; }
.pending-remove:hover { color: #ef4444; background: #fee2e2; }

/* Input area */
.input-area { display: flex; gap: 8px; padding: 12px 16px 16px; border-top: 1px solid #e5e7eb; background: #fff; }
.attach-btn { background: none; border: 1px solid #d1d5db; border-radius: 10px; padding: 10px; cursor: pointer; color: #9ca3af; display: flex; align-items: center; transition: all 0.12s; flex-shrink: 0; }
.attach-btn:hover { color: #6366f1; border-color: #6366f1; background: rgba(99,102,241,0.05); }
.input-box { flex: 1; padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 14px; resize: none; outline: none; min-height: 44px; max-height: 160px; font-family: inherit; line-height: 1.5; }
.input-box:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
.send-btn { padding: 10px 16px; border: none; border-radius: 10px; background: #6366f1; color: #fff; cursor: pointer; transition: background 0.12s; display: flex; align-items: center; flex-shrink: 0; }
.send-btn:hover:not(:disabled) { background: #4f46e5; }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
