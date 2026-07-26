<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useMonitoringStore } from '@/stores/monitoring'
import { monitoringApi } from '@/api/monitoring'
import DataChart from '@/components/DataChart.vue'
import { Activity, BarChart3, MapPin, TrendingUp, RefreshCw, Loader2 } from 'lucide-vue-next'

const store = useMonitoringStore()
const selectedStationId = ref(null)
const selectedStationCode = ref('')

const typeLabels = {
  groundwater: { label: 'Groundwater', icon: '��', unit: 'm' },
  rainfall: { label: 'Rainfall', icon: '��', unit: 'mm' },
  pore_pressure: { label: 'Pore Pressure', icon: '��', unit: 'kPa' },
  gnss: { label: 'GNSS', icon: '��', unit: 'mm' },
  insar: { label: 'InSAR', icon: '��', unit: 'mm' },
}

onMounted(() => {
  store.fetchAllSummaries()
  store.fetchStations()
})

watch(() => store.activeType, () => {
  selectedStationId.value = null
  store.chartData = []
  store.stats = null
})

async function selectStation(station) {
  selectedStationId.value = station.id
  selectedStationCode.value = station.station_code
  store.fetchData(store.activeType, { stationId: station.id })
  store.fetchStats(store.activeType, { stationId: station.id })
}

function refreshAll() {
  store.fetchAllSummaries()
  store.fetchStations()
}
</script>

<template>
  <div class="monitoring-view">
    <div class="page-header">
      <div>
        <h2>Monitoring Dashboard</h2>
        <p class="page-desc">Geological deformation & hydrological monitoring data</p>
      </div>
      <button class="btn btn-ghost" @click="refreshAll">
        <RefreshCw :size="14" />
        Refresh
      </button>
    </div>

    <!-- Summary Cards -->
    <div class="summary-grid">
      <div
        v-for="(info, type) in typeLabels"
        :key="type"
        class="summary-card"
        :class="{ active: store.activeType === type }"
        @click="store.setActiveType(type)"
      >
        <div class="sc-head">
          <span class="sc-label">{{ info.label }}</span>
          <span class="sc-icon">{{ info.icon }}</span>
        </div>
        <div class="sc-stats">
          <div class="sc-stat">
            <span class="sc-val">{{ store.summaries[type]?.station_count ?? '-' }}</span>
            <span class="sc-desc">Stations</span>
          </div>
          <div class="sc-stat">
            <span class="sc-val">{{ store.summaries[type]?.total_records ?? '-' }}</span>
            <span class="sc-desc">records</span>
          </div>
        </div>
      </div>
    </div>

    <div class="dashboard-body">
      <!-- Left: Station List -->
      <div class="panel station-panel">
        <div class="panel-header">
          <MapPin :size="16" />
          <span>{{ typeLabels[store.activeType]?.label }} Stations</span>
          <span class="badge">{{ store.filteredStations.length }}</span>
        </div>
        <div class="panel-body">
          <div v-if="store.StationsLoading" class="loading-inline">
            <Loader2 :size="14" class="spin" /> Loading...
          </div>
          <div v-else-if="store.filteredStations.length === 0" class="empty-inline">
            No Stations for this type
          </div>
          <div
            v-for="s in store.filteredStations"
            :key="s.id"
            class="station-item"
            :class="{ active: s.id === selectedStationId }"
            @click="selectStation(s)"
          >
            <div class="si-code">{{ s.station_code }}</div>
            <div class="si-name">{{ s.station_name || s.station_code }}</div>
            <div v-if="s.status === 'inactive'" class="si-status inactive">inactive</div>
          </div>
        </div>
      </div>

      <!-- Right: Data Panel -->
      <div class="panel data-panel">
        <div class="panel-header">
          <Activity :size="16" />
          <span>{{ selectedStationCode || 'Select a station' }}</span>
          <span v-if="store.dataLoading" class="badge loading"><Loader2 :size="12" class="spin" /></span>
          <span v-else-if="store.chartData.length" class="badge">{{ store.chartData.length }} points</span>
        </div>
        <DataChart
          :records="store.chartData"
          :data-type="store.activeType"
          :title="typeLabels[store.activeType]?.label"
        />

        <!-- Statistics -->
        <div v-if="store.stats" class="stats-row">
          <div class="stat-item">
            <span class="stat-label">Mean</span>
            <span class="stat-value">{{ store.stats.mean != null ? Number(store.stats.mean).toFixed(3) : '-' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Min</span>
            <span class="stat-value">{{ store.stats.min != null ? Number(store.stats.min).toFixed(3) : '-' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Max</span>
            <span class="stat-value">{{ store.stats.max != null ? Number(store.stats.max).toFixed(3) : '-' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Std</span>
            <span class="stat-value">{{ store.stats.std != null ? Number(store.stats.std).toFixed(3) : '-' }}</span>
          </div>
        </div>

        <!-- Data Table -->
        <div v-if="store.chartData.length" class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th v-for="(v, k) in store.chartData[0]?.values" :key="k">{{ k }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in store.chartData.slice(0, 15)" :key="r.id">
                <td>{{ new Date(r.measurement_time).toLocaleString('zh-CN') }}</td>
                <td v-for="(v, k) in r.values" :key="k">{{ v != null ? Number(v).toFixed(3) : '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="store.chartData.length > 15" class="table-more">
            Showing 15 of {{ store.chartData.length }} records
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitoring-view { padding: 24px; max-width: 1200px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 2px; font-size: 20px; color: #111; }
.page-desc { margin: 0; color: #666; font-size: 13px; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 8px; border: none; font-size: 13px; cursor: pointer; white-space: nowrap; }
.btn-ghost { background: #fff; color: #555; border: 1px solid #e5e7eb; }
.btn-ghost:hover { background: #f5f5f7; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* Summary cards */
.summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 20px; }
.summary-card {
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 14px 16px; cursor: pointer; transition: all 0.12s;
}
.summary-card:hover { border-color: #c0c0d0; }
.summary-card.active { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,0.15); }
.sc-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.sc-label { font-size: 12px; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: 0.3px; }
.sc-icon { font-size: 18px; }
.sc-stats { display: flex; gap: 16px; }
.sc-stat { display: flex; flex-direction: column; }
.sc-val { font-size: 20px; font-weight: 700; color: #111; line-height: 1.2; }
.sc-desc { font-size: 11px; color: #999; }

/* Panels */
.dashboard-body { display: grid; grid-template-columns: 260px 1fr; gap: 16px; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
.panel-header {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 14px; border-bottom: 1px solid #e5e7eb;
  font-size: 13px; font-weight: 500; color: #333;
}
.badge {
  margin-left: auto; font-size: 11px; background: #f0f0f0; padding: 1px 8px;
  border-radius: 10px; color: #666; font-weight: 400;
}
.badge.loading { background: transparent; padding: 0; }
.panel-body { padding: 6px; max-height: 400px; overflow-y: auto; }

/* Station list */
.station-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  font-size: 13px; transition: all 0.1s;
}
.station-item:hover { background: #f5f5f7; }
.station-item.active { background: rgba(99,102,241,0.08); }
.si-code { font-family: monospace; font-weight: 600; color: #333; min-width: 60px; }
.si-name { color: #888; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.si-status.inactive { font-size: 10px; color: #ef4444; background: #fee2e2; padding: 1px 6px; border-radius: 8px; }

/* Data panel */
.data-panel { display: flex; flex-direction: column; }

/* Stats */
.stats-row {
  display: flex; gap: 0;
  border-top: 1px solid #e5e7eb; border-bottom: 1px solid #e5e7eb;
}
.stat-item {
  flex: 1; text-align: center; padding: 10px 6px;
  border-right: 1px solid #e5e7eb;
}
.stat-item:last-child { border-right: none; }
.stat-label { display: block; font-size: 11px; color: #999; margin-bottom: 2px; }
.stat-value { display: block; font-size: 15px; font-weight: 600; color: #333; }

/* Table */
.data-table-wrap { padding: 10px 14px; max-height: 300px; overflow: auto; }
.data-table { width: 100%; font-size: 12px; border-collapse: collapse; }
.data-table th { text-align: left; padding: 6px 8px; font-weight: 600; color: #555; border-bottom: 1px solid #e5e7eb; white-space: nowrap; }
.data-table td { padding: 5px 8px; border-bottom: 1px solid #f0f0f0; white-space: nowrap; }
.data-table tr:hover td { background: #f9fafb; }
.table-more { font-size: 11px; color: #999; padding: 8px 0 0; text-align: center; }
.loading-inline, .empty-inline { padding: 20px; text-align: center; color: #999; font-size: 13px; display: flex; align-items: center; justify-content: center; gap: 6px; }
</style>
