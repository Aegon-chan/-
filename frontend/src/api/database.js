import request from './request'

export const dbApi = {
  tables() {
    return request.get('/db/tables')
  },
  stats() {
    return request.get('/db/stats/all')
  },
  browse(db, table, { page = 1, pageSize = 50, search = '' } = {}) {
    return request.get(`/db/${db}/${table}`, { params: { page, page_size: pageSize, search } })
  },
  query(sql, database = 'main') {
    return request.post('/db/query', { sql, database })
  },
  batchDelete(db, table, ids) {
    return request.delete(`/db/${db}/${table}/batch-delete`, { data: { ids } })
  },
  deleteByCondition(db, table, condition) {
    return request.post(`/db/${db}/${table}/delete-by-condition`, condition)
  },
  importPreview(db, table, file) {
    const form = new FormData()
    form.append('file', file)
    return request.post(`/db/${db}/${table}/import/preview`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  importData(db, table, file) {
    const form = new FormData()
    form.append('file', file)
    return request.post(`/db/${db}/${table}/import`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000,
    })
  },
}
