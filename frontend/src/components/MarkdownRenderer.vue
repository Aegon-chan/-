<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js'

marked.use(markedHighlight({
  langPrefix: 'hljs language-',
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try { return hljs.highlight(code, { language: lang }).value }
      catch (_) {}
    }
    return hljs.highlightAuto(code).value
  }
}))

marked.setOptions({
  breaks: true,
  gfm: true,
})

const props = defineProps({ content: { type: String, default: '' } })
const rendered = computed(() => {
  if (!props.content) return ''
  return marked.parse(props.content)
})
</script>

<template>
  <div class="markdown-body" v-html="rendered" />
</template>

<style>
.markdown-body { line-height: 1.7; font-size: 14px; word-break: break-word; }
.markdown-body p { margin: 0 0 8px; }
.markdown-body p:last-child { margin-bottom: 0; }
.markdown-body pre { background: #f6f8fa; border-radius: 8px; padding: 14px; overflow-x: auto; margin: 8px 0; font-size: 13px; }
.markdown-body code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; }
.markdown-body :not(pre) > code { background: #f0f1f3; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #d63384; }
.markdown-body ul, .markdown-body ol { padding-left: 20px; margin: 4px 0 8px; }
.markdown-body li { margin: 2px 0; }
.markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 { margin: 16px 0 8px; font-weight: 600; color: #111; }
.markdown-body h1 { font-size: 18px; }
.markdown-body h2 { font-size: 16px; }
.markdown-body h3 { font-size: 15px; }
.markdown-body blockquote { border-left: 3px solid #d0d7de; padding-left: 12px; color: #57606a; margin: 8px 0; }
.markdown-body table { border-collapse: collapse; margin: 8px 0; width: 100%; }
.markdown-body th, .markdown-body td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
.markdown-body th { background: #f6f8fa; font-weight: 600; }
.markdown-body a { color: #0969da; text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body hr { border: none; border-top: 1px solid #d0d7de; margin: 16px 0; }
.markdown-body table { border-collapse: collapse; margin: 8px 0; width: 100%; }
.markdown-body th, .markdown-body td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
.markdown-body th { background: #f6f8fa; font-weight: 600; }
</style>
