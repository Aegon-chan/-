<script setup>
import { ref, computed } from 'vue'
import { Line, Bar, Scatter } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  Title, Tooltip, Legend, Filler, TimeScale, RadialLinearScale,
} from 'chart.js'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  Title, Tooltip, Legend, Filler
)

const chartType = ref('timeseries')
const colorScheme = ref('default')
const showGrid = ref(true)
const showLegend = ref(true)
const addAnnotation = ref('')
const figWidth = ref(7)
const figHeight = ref(4)

const sampleData = computed(() => {
  const n = 30
  const labels = Array.from({ length: n }, (_, i) => `P${i + 1}`)
  const a = Array.from({ length: n }, (_, i) => Math.sin(i * 0.5) + (Math.random() - 0.5) * 0.3)
  const b = Array.from({ length: n }, (_, i) => Math.cos(i * 0.5) + (Math.random() - 0.5) * 0.3)
  return { labels, a, b }
})

const colors = {
  default: { a: '#6366f1', b: '#f59e0b', bg: 'rgba(99,102,241,0.08)' },
  warm: { a: '#ef4444', b: '#f97316', bg: 'rgba(239,68,68,0.08)' },
  cool: { a: '#06b6d4', b: '#8b5cf6', bg: 'rgba(6,182,212,0.08)' },
  mono: { a: '#1f2937', b: '#9ca3af', bg: 'rgba(31,41,55,0.08)' },
}

const pal = computed(() => colors[colorScheme.value] || colors.default)

const chartData = computed(() => ({
  labels: sampleData.value.labels,
  datasets: [
    { label: 'Series A', data: sampleData.value.a, borderColor: pal.value.a, backgroundColor: pal.value.a, fill: false, tension: 0.3, pointRadius: 3 },
    { label: 'Series B', data: sampleData.value.b, borderColor: pal.value.b, backgroundColor: pal.value.b, fill: false, tension: 0.3, pointRadius: 3 },
  ],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: showLegend.value, position: 'bottom', labels: { boxWidth: 12, padding: 12, font: { size: 11 } } },
    tooltip: { backgroundColor: '#1a1a2e', titleFont: { size: 12 }, bodyFont: { size: 12 }, padding: 10, cornerRadius: 6 },
  },
  scales: {
    x: { grid: { display: showGrid.value, color: 'rgba(0,0,0,0.05)' }, ticks: { font: { size: 10 } } },
    y: { grid: { display: showGrid.value, color: 'rgba(0,0,0,0.05)' }, ticks: { font: { size: 10 } } },
  },
}))

function exportPng() {
  const canvas = document.querySelector('.chart-render canvas')
  if (!canvas) return
  const link = document.createElement('a')
  link.download = 'chart.png'
  link.href = canvas.toDataURL('image/png')
  link.click()
}

function regenerate() {}
</script>

<template>
  <div class="chart-view">
    <div class="page-header">
      <div><h2>Chart Studio</h2><p class="page-desc">Configure and preview charts before exporting</p></div>
    </div>

    <div class="chart-layout">
      <!-- Controls -->
      <div class="controls-panel">
        <div class="control-group">
          <label class="ctrl-label">Chart Type</label>
          <select v-model="chartType" class="select">
            <option value="timeseries">Time Series (Line)</option>
            <option value="bar">Bar Chart</option>
            <option value="scatter">Scatter</option>
          </select>
        </div>
        <div class="control-group">
          <label class="ctrl-label">Color Scheme</label>
          <select v-model="colorScheme" class="select">
            <option value="default">Default (Indigo/Amber)</option>
            <option value="warm">Warm (Red/Orange)</option>
            <option value="cool">Cool (Cyan/Purple)</option>
            <option value="mono">Monochrome</option>
          </select>
        </div>
        <div class="control-group">
          <label class="ctrl-label">Display</label>
          <label class="toggle-row"><input type="checkbox" v-model="showGrid" /> Show Grid</label>
          <label class="toggle-row"><input type="checkbox" v-model="showLegend" /> Show Legend</label>
        </div>
        <div class="control-group">
          <label class="ctrl-label">Figure Size</label>
          <div class="size-row">
            <span>W</span><input type="range" v-model.number="figWidth" min="4" max="12" step="0.5" class="range" /><span>{{ figWidth }}</span>
          </div>
          <div class="size-row">
            <span>H</span><input type="range" v-model.number="figHeight" min="3" max="9" step="0.5" class="range" /><span>{{ figHeight }}</span>
          </div>
        </div>
        <div class="control-group">
          <label class="ctrl-label">Annotation (label)</label>
          <input v-model="addAnnotation" class="input" placeholder="e.g. Peak value observed" />
        </div>
        <div class="control-actions">
          <button class="btn btn-primary" @click="exportPng">Export PNG</button>
          <button class="btn btn-ghost" @click="regenerate">Regenerate Data</button>
        </div>
      </div>

      <!-- Preview -->
      <div class="preview-panel">
        <div class="chart-render" :style="{ height: figHeight * 60 + 'px' }">
          <Line v-if="chartType === 'timeseries'" :data="chartData" :options="chartOptions" />
          <Bar v-else-if="chartType === 'bar'" :data="chartData" :options="chartOptions" />
          <Line v-else :data="chartData" :options="chartOptions" />
        </div>
        <div v-if="addAnnotation" class="annotation-note">
          <span class="ann-label">Annotation:</span> {{ addAnnotation }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-view { padding: 24px; max-width: 1000px; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin:0 0 2px; font-size:20px; color:#111; }
.page-desc { margin:0; color:#666; font-size:13px; }
.btn { display:inline-flex; align-items:center; gap:6px; padding:7px 14px; border-radius:8px; border:none; font-size:13px; cursor:pointer; white-space:nowrap; }
.btn-ghost { background:#fff; color:#555; border:1px solid #e5e7eb; }
.btn-ghost:hover { background:#f5f5f7; }
.btn-primary { background:#6366f1; color:#fff; }
.btn-primary:hover { background:#4f46e5; }
.select { width:100%; padding:7px 10px; border:1px solid #d1d5db; border-radius:6px; font-size:13px; outline:none; background:#fff; }
.select:focus { border-color:#6366f1; }
.input { width:100%; padding:7px 10px; border:1px solid #d1d5db; border-radius:6px; font-size:13px; outline:none; box-sizing:border-box; }
.input:focus { border-color:#6366f1; }

.chart-layout { display:grid; grid-template-columns:240px 1fr; gap:20px; align-items:start; }
.controls-panel { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px; }
.control-group { margin-bottom:14px; }
.ctrl-label { display:block; font-size:11px; font-weight:600; color:#555; margin-bottom:5px; text-transform:uppercase; letter-spacing:0.3px; }
.toggle-row { display:flex; align-items:center; gap:6px; font-size:13px; color:#333; padding:3px 0; cursor:pointer; }
.toggle-row input { width:14px; height:14px; }
.size-row { display:flex; align-items:center; gap:8px; font-size:12px; color:#555; margin-bottom:4px; }
.size-row span { min-width:12px; }
.range { flex:1; height:4px; accent-color:#6366f1; }
.control-actions { display:flex; flex-direction:column; gap:6px; }

.preview-panel { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:16px; }
.chart-render { position:relative; min-height:200px; }
.annotation-note { margin-top:10px; padding:8px 12px; background:#f0f4ff; border-radius:6px; font-size:12px; color:#4338ca; }
.ann-label { font-weight:600; color:#6366f1; }
</style>
