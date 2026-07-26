<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler, TimeScale,
} from 'chart.js'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler, TimeScale
)

const props = defineProps({
  records: { type: Array, default: () => [] },
  dataType: { type: String, default: '' },
  valueField: { type: String, default: 'value' },
  title: { type: String, default: '' },
})

const typeColors = {
  groundwater: { border: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
  rainfall: { border: '#10b981', bg: 'rgba(16,185,129,0.1)' },
  pore_pressure: { border: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
  gnss: { border: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
  insar: { border: '#8b5cf6', bg: 'rgba(139,92,246,0.1)' },
}

const color = computed(() => typeColors[props.dataType] || typeColors.groundwater)

const chartData = computed(() => ({
  labels: props.records.map((r) => {
    const d = new Date(r.measurement_time)
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit' })
  }),
  datasets: [{
    label: props.title || props.dataType,
    data: props.records.map((r) => {
      const v = r.values?.[props.valueField]
      return v != null ? Number(v) : null
    }),
    borderColor: color.value.border,
    backgroundColor: color.value.bg,
    fill: true,
    tension: 0.3,
    pointRadius: 3,
    pointHoverRadius: 5,
    borderWidth: 2,
  }],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: 'index' },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#1a1a2e',
      titleFont: { size: 12 },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 8,
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { font: { size: 11 }, maxRotation: 45 },
    },
    y: {
      grid: { color: 'rgba(0,0,0,0.06)' },
      ticks: { font: { size: 11 } },
    },
  },
}

const hasData = computed(() => props.records.length > 0)
</script>

<template>
  <div class="chart-container" :class="{ empty: !hasData }">
    <div v-if="!hasData" class="chart-empty">
      <p>Select a station and time range to view data</p>
    </div>
    <Line v-else :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
.chart-container {
  height: 280px;
  padding: 8px;
  position: relative;
}
.chart-container.empty {
  display: flex;
  align-items: center;
  justify-content: center;
}
.chart-empty {
  color: #999;
  font-size: 13px;
  text-align: center;
}
</style>
