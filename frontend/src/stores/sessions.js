import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { sessionApi } from '@/api/sessions'

export const useSessionsStore = defineStore('sessions', () => {
  const list = ref([])
  const total = ref(0)
  const currentId = ref(null)
  const loading = ref(false)

  const currentSession = computed(() =>
    list.value.find((s) => s.id === currentId.value) || null
  )

  async function fetchList() {
    loading.value = true
    try {
      const res = await sessionApi.list()
      list.value = res.sessions || []
      total.value = res.total || 0
    } finally {
      loading.value = false
    }
  }

  async function createSession(title) {
    const res = await sessionApi.create(title)
    list.value.unshift(res)
    currentId.value = res.id
    total.value++
    return res
  }

  async function deleteSession(id) {
    await sessionApi.delete(id)
    list.value = list.value.filter((s) => s.id !== id)
    total.value = Math.max(0, total.value - 1)
    if (currentId.value === id) currentId.value = null
  }

  function selectSession(id) {
    currentId.value = id
  }

  return { list, total, currentId, currentSession, loading, fetchList, createSession, deleteSession, selectSession }
})
