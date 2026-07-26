import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { monitoringApi } from '@/api/monitoring'

const DATA_TYPES = ['groundwater', 'rainfall', 'pore_pressure', 'gnss', 'insar']

export const useMonitoringStore = defineStore('monitoring', () => {
  const activeType = ref('groundwater')
  const summaries = ref({})
  const allStations = ref([])
  const stationsLoading = ref(false)
  const dataLoading = ref(false)
  const chartData = ref([])
  const stats = ref(null)

  const filteredStations = computed(() =>
    allStations.value.filter((s) => s.station_type === activeType.value)
  )

  async function fetchSummary(dataType) {
    try {
      const res = await monitoringApi.summary(dataType)
      summaries.value[dataType] = res
    } catch (_) {
      summaries.value[dataType] = { total_records: 0, station_count: 0, time_range: {} }
    }
  }

  async function fetchAllSummaries() {
    await Promise.all(DATA_TYPES.map((t) => fetchSummary(t)))
  }

  async function fetchStations() {
    stationsLoading.value = true
    try {
      const res = await monitoringApi.stations()
      allStations.value = res || []
    } finally {
      stationsLoading.value = false
    }
  }

  async function fetchData(dataType, { stationId, start, end } = {}) {
    dataLoading.value = true
    try {
      const res = await monitoringApi.queryData(dataType, { stationId, start, end })
      chartData.value = res.records || []
    } finally {
      dataLoading.value = false
    }
  }

  async function fetchStats(dataType, opts = {}) {
    try {
      const res = await monitoringApi.statistics(dataType, opts)
      stats.value = res
    } catch (_) { stats.value = null }
  }

  function setActiveType(t) { activeType.value = t }

  return {
    activeType, summaries, allStations, stationsLoading, dataLoading, chartData, stats,
    filteredStations, fetchSummary, fetchAllSummaries, fetchStations, fetchData, fetchStats, setActiveType,
  }
})
