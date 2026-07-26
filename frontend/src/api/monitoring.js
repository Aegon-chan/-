import request from './request'

export const monitoringApi = {
  stations(type) {
    const params = type ? { type } : {}
    return request.get('/monitoring/stations', { params })
  },
  station(id) {
    return request.get(`/monitoring/stations/${id}`)
  },
  summary(dataType) {
    return request.get(`/monitoring/data/${dataType}/summary`)
  },
  latest(dataType) {
    return request.get(`/monitoring/data/${dataType}/latest`)
  },
  statistics(dataType, { stationId, start, end } = {}) {
    return request.get(`/monitoring/data/${dataType}/statistics`, {
      params: { station_id: stationId, start, end },
    })
  },
  queryData(dataType, { stationId, start, end, limit = 200, offset = 0 } = {}) {
    return request.get(`/monitoring/data/${dataType}`, {
      params: { station_id: stationId, start, end, limit, offset },
    })
  },
}
