<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { configApi } from '@/api/config'
import { modelApi } from '@/api/models'
import { useSettingsStore } from '@/stores/settings'
import { Settings, Key, Cpu, Save, Globe, Check, Loader2 } from 'lucide-vue-next'

const { t } = useI18n()
const settingsStore = useSettingsStore()
const apiKeys = ref({ deepseek: '', kimi: '', openai: '' })
const models = ref([])
const savingKey = ref(false)
const savedKeys = ref(false)
const loading = ref(true)

const languages = [
  { id: 'zh-CN', label: '\u4e2d\u6587' },
  { id: 'en', label: 'English' },
  { id: 'ja', label: '\u65e5\u672c\u8a9e' },
  { id: 'ru', label: '\u0420\u0443\u0441\u0441\u043a\u0438\u0439' },
]

onMounted(async () => {
  try {
    const [keyRes, modelRes] = await Promise.all([
      configApi.getApiKeys(),
      modelApi.list(),
    ])
    if (keyRes) {
      apiKeys.value = {
        deepseek: keyRes.deepseek ? '*** configured ***' : '',
        kimi: keyRes.kimi ? '*** configured ***' : '',
        openai: keyRes.openai ? '*** configured ***' : '',
      }
    }
    models.value = modelRes.models || []
  } catch (_) {}
  finally { loading.value = false }
})

async function saveKeys() {
  savingKey.value = true
  savedKeys.value = false
  try {
    await configApi.updateApiKeys({
      deepseek: apiKeys.value.deepseek,
      kimi: apiKeys.value.kimi,
      openai: apiKeys.value.openai,
    })
    savedKeys.value = true
    setTimeout(() => { savedKeys.value = false }, 2000)
  } finally { savingKey.value = false }
}

function changeLocale(lang) {
  settingsStore.setLocale(lang)
}

const modelProviders = [
  { key: 'deepseek', name: 'DeepSeek', url: 'https://api.deepseek.com' },
  { key: 'kimi', name: 'Kimi (Moonshot)', url: 'https://api.moonshot.cn' },
  { key: 'openai', name: 'OpenAI', url: 'https://api.openai.com/v1' },
]
</script>

<template>
  <div class="settings-view">
    <div class="page-header">
      <h2>{{ t('settings.title') }}</h2>
    </div>

    <div v-if="loading" class="loading"><Loader2 :size="18" class="spin" /> {{ t('common.loading') }}</div>

    <template v-else>
      <!-- Language -->
      <section class="section">
        <div class="section-header">
          <Globe :size="18" />
          <h3>{{ t('settings.languageSettings') }}</h3>
        </div>
        <div class="lang-list">
          <button
            v-for="lang in languages"
            :key="lang.id"
            class="lang-btn"
            :class="{ active: settingsStore.locale === lang.id }"
            @click="changeLocale(lang.id)"
          >
            <Check v-if="settingsStore.locale === lang.id" :size="14" class="lang-check" />
            {{ lang.label }}
          </button>
        </div>
      </section>

      <!-- API Keys -->
      <section class="section">
        <div class="section-header">
          <Key :size="18" />
          <h3>{{ t('settings.apiKeys') }}</h3>
        </div>
        <div class="key-list">
          <div v-for="p in modelProviders" :key="p.key" class="key-row">
            <div class="key-info">
              <span class="key-name">{{ p.name }}</span>
              <span class="key-url">{{ p.url }}</span>
            </div>
            <input
              v-model="apiKeys[p.key]"
              class="key-input"
              :placeholder="'Enter ' + p.name + ' API key'"
              type="password"
            />
          </div>
        </div>
        <button class="btn btn-primary" @click="saveKeys" :disabled="savingKey">
          <Loader2 v-if="savingKey" :size="14" class="spin" />
          <Save v-else :size="14" />
          {{ savingKey ? t('settings.saving') : t('settings.saveKeys') }}
        </button>
        <span v-if="savedKeys" class="saved-badge"><Check :size="14" /> {{ t('settings.saved') }}</span>
      </section>

      <!-- Models -->
      <section class="section">
        <div class="section-header">
          <Cpu :size="18" />
          <h3>{{ t('settings.availableModels') }}</h3>
        </div>
        <div v-if="models.length === 0" class="empty-hint">{{ t('settings.noModels') }}</div>
        <div v-else class="model-list">
          <div v-for="m in models" :key="m.model_id" class="model-item">
            <span class="model-id">{{ m.model_id }}</span>
            <span class="model-type">{{ m.type || 'llm' }}</span>
            <span class="model-status" :class="m.status || 'active'">{{ m.status || 'active' }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.settings-view { padding: 24px; max-width: 680px; }
.page-header h2 { margin: 0 0 24px; font-size: 20px; color: #111; }
.loading { display: flex; align-items: center; gap: 8px; color: #888; font-size: 13px; padding: 40px 0; justify-content: center; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }
.section { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.section-header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; color: #333; }
.section-header h3 { margin: 0; font-size: 15px; font-weight: 600; }
.lang-list { display: flex; gap: 8px; flex-wrap: wrap; }
.lang-btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 18px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; color: #333; font-size: 14px; cursor: pointer; transition: all 0.12s; }
.lang-btn:hover { border-color: #6366f1; color: #6366f1; }
.lang-btn.active { border-color: #6366f1; background: rgba(99,102,241,0.06); color: #6366f1; font-weight: 500; }
.lang-check { color: #6366f1; }
.key-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.key-row { display: flex; align-items: center; gap: 10px; }
.key-info { min-width: 140px; }
.key-name { font-size: 13px; font-weight: 500; color: #333; display: block; }
.key-url { font-size: 11px; color: #999; }
.key-input { flex: 1; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; outline: none; font-family: inherit; }
.key-input:focus { border-color: #6366f1; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; border: none; font-size: 13px; cursor: pointer; white-space: nowrap; }
.btn-primary { background: #6366f1; color: #fff; }
.btn-primary:hover { background: #4f46e5; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.saved-badge { display: inline-flex; align-items: center; gap: 4px; margin-left: 10px; color: #059669; font-size: 13px; }
.model-list { display: flex; flex-direction: column; gap: 4px; }
.model-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; background: #f9fafb; border-radius: 6px; }
.model-id { flex: 1; font-size: 13px; font-family: monospace; color: #333; }
.model-type { font-size: 11px; color: #888; background: #f0f0f0; padding: 2px 8px; border-radius: 10px; }
.model-status { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.model-status.active { background: #d1fae5; color: #059669; }
.model-status.inactive { background: #fee2e2; color: #dc2626; }
.empty-hint { padding: 10px 0; color: #999; font-size: 13px; }
</style>
