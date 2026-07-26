import { createI18n } from 'vue-i18n'
import en from './locales/en.js'
import zhCN from './locales/zh-CN.js'
import ja from './locales/ja.js'
import ru from './locales/ru.js'

function getInitialLocale() {
  try {
    const saved = localStorage.getItem('locale')
    if (saved && ['zh-CN', 'en', 'ja', 'ru'].includes(saved)) return saved
  } catch (_) {}
  return navigator.language?.startsWith('zh') ? 'zh-CN' :
         navigator.language?.startsWith('ja') ? 'ja' :
         navigator.language?.startsWith('ru') ? 'ru' : 'en'
}

const i18n = createI18n({
  locale: getInitialLocale(),
  fallbackLocale: 'en',
  legacy: false,
  globalInjection: true,
  messages: { en, 'zh-CN': zhCN, ja, ru },
})

export default i18n
