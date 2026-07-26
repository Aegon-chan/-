import { defineStore } from 'pinia'
import { ref } from 'vue'
import { modelApi } from '@/api/models'

export const useModelsStore = defineStore('models', () => {
  const models = ref([])
  const defaultLlm = ref('')
  const loading = ref(false)

  async function fetchModels() {
    loading.value = true
    try {
      const res = await modelApi.list()
      models.value = res.models || []
      defaultLlm.value = res.default_llm || ''
    } finally {
      loading.value = false
    }
  }

  return { models, defaultLlm, loading, fetchModels }
})
