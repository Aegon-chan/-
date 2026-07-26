import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const locale = ref('zh-CN')

  function setLocale(lang) {
    locale.value = lang
    try { localStorage.setItem('locale', lang) } catch (_) {}
    // Dynamic import to change vue-i18n locale
    import('@/i18n').then((m) => {
      m.default.global.locale.value = lang
    })
  }

  // Initialize from localStorage
  try {
    const saved = localStorage.getItem('locale')
    if (saved && ['zh-CN', 'en', 'ja', 'ru'].includes(saved)) {
      locale.value = saved
    }
  } catch (_) {}

  return { locale, setLocale }
})
