<script setup>
import { onMounted, watch } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatStore } from '@/stores/chat'
import { useRouter } from 'vue-router'
import { sessionApi } from '@/api/sessions'
import { Plus, Trash2, MessageSquare } from 'lucide-vue-next'

const store = useSessionsStore()
const chatStore = useChatStore()
const router = useRouter()

onMounted(() => { store.fetchList() })

const emit = defineEmits(['select-session'])

async function createSession() {
  const res = await store.createSession('New Conversation')
  chatStore.clearMessages()
  router.push({ name: 'Chat' })
  emit('select-session', res.id)
}

async function deleteSession(id, e) {
  e.stopPropagation()
  if (store.currentId === id) {
    chatStore.clearMessages()
  }
  await store.deleteSession(id)
}

async function selectSession(id) {
  store.selectSession(id)
  try {
    const detail = await sessionApi.get(id)
    chatStore.setMessages(detail.messages || [])
  } catch (_) {
    chatStore.clearMessages()
  }
  router.push({ name: 'Chat' })
  emit('select-session', id)
}
</script>

<template>
  <div class="session-list">
    <div class="session-header">
      <span class="session-title">{{ $t('session.conversations') }}</span>
      <button class="new-btn" @click="createSession" :title="$t('session.newConversation')">
        <Plus :size="16" />
      </button>
    </div>
    <div class="list">
      <div
        v-for="s in store.list"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === store.currentId }"
        @click="selectSession(s.id)"
      >
        <MessageSquare :size="14" class="item-icon" />
        <span class="item-title">{{ s.title || 'Untitled' }}</span>
        <button class="del-btn" @click="deleteSession(s.id, $event)" title="Delete">
          <Trash2 :size="12" />
        </button>
      </div>
      <div v-if="store.list.length === 0" class="empty-hint">
        {{ $t('session.noConversations') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-list {
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 8px;
}
.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
}
.session-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #6b7280;
  font-weight: 600;
}
.new-btn {
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
}
.new-btn:hover { background: rgba(255,255,255,0.08); color: #fff; }
.list { padding: 0 8px; }
.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #c0c0d0;
  transition: all 0.12s;
  margin-bottom: 2px;
}
.session-item:hover { background: rgba(255,255,255,0.06); color: #fff; }
.session-item.active { background: rgba(99,102,241,0.2); color: #818cf8; }
.item-icon { flex-shrink: 0; opacity: 0.6; }
.item-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.del-btn {
  background: none; border: none; color: #6b7280; cursor: pointer;
  padding: 2px; border-radius: 3px; opacity: 0; transition: opacity 0.12s;
  flex-shrink: 0; display: flex;
}
.session-item:hover .del-btn { opacity: 1; }
.del-btn:hover { color: #ef4444; background: rgba(239,68,68,0.15); }
.empty-hint { padding: 20px 10px; text-align: center; color: #6b7280; font-size: 12px; }
</style>
