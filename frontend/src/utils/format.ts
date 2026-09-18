/** Unified time formatting (spec §20):
 *  <1min -> 刚刚 | today -> 今天 HH:mm | yesterday -> 昨天 HH:mm
 *  last 7 days -> 星期X HH:mm | older -> YYYY-MM-DD HH:mm
 *  Hover/title shows full ISO time.
 */
export function formatTime(input: string | Date | null | undefined): string {
  if (!input) return '-'
  const d = typeof input === 'string' ? new Date(input) : input
  if (isNaN(d.getTime())) return '-'
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const oneMin = 60 * 1000
  const pad = (n: number) => String(n).padStart(2, '0')
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startOfYesterday = startOfToday - 24 * 3600 * 1000
  if (diff < oneMin && diff >= 0) return '刚刚'
  if (d.getTime() >= startOfToday) return `今天 ${hm}`
  if (d.getTime() >= startOfYesterday) return `昨天 ${hm}`
  const weekAgo = startOfToday - 6 * 24 * 3600 * 1000
  if (d.getTime() >= weekAgo) {
    const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
    return `${weekdays[d.getDay()]} ${hm}`
  }
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${hm}`
}

export function formatDate(input: string | null | undefined): string {
  if (!input) return '-'
  const d = new Date(input)
  if (isNaN(d.getTime())) return input
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const STATUS_LABELS: Record<string, string> = {
  READY: 'READY',
  UPDATING: 'UPDATING',
  PARTIAL: 'PARTIAL',
  EMPTY: 'EMPTY',
  NEEDS_REINDEX: '待重建索引',
  UPLOADED: '已上传',
  PARSING: '解析中',
  CHUNKING: '切片中',
  INDEXING: '索引中',
  FAILED: '失败',
  CURRENT: '当前生效 · READY',
  HISTORICAL: '历史版',
  SUFFICIENT: '已检索到相关资料',
  INSUFFICIENT: '相关资料不足',
  CONFLICTING: '发现来源信息不一致',
}

export function statusClass(status: string | null | undefined): string {
  switch ((status || '').toUpperCase()) {
    case 'READY':
    case 'SUFFICIENT':
    case 'CURRENT':
      return 'status-ready'
    case 'UPDATING':
    case 'PARSING':
    case 'CHUNKING':
    case 'INDEXING':
    case 'UPLOADED':
    case 'NEEDS_REINDEX':
      return 'status-updating'
    case 'PARTIAL':
      return 'status-partial'
    case 'FAILED':
    case 'CONFLICTING':
      return 'status-failed'
    case 'INSUFFICIENT':
      return 'status-processing'
    case 'HISTORICAL':
      return 'status-historical'
    default:
      return 'status-empty'
  }
}
