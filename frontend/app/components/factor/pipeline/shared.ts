export type FactorPipelineView = 'research' | 'deployments' | 'live-gate'

export interface FactorLiveCheckRow {
  key: string
  label: string
  actual: unknown
  threshold: unknown
  passed: boolean
}

export function formatTimestamp(ts: number | null | undefined): string {
  if (!ts) return '--'
  return new Date(ts * 1000).toLocaleString()
}

export function formatIso(ts: string | null | undefined): string {
  if (!ts) return '--'
  return new Date(ts).toLocaleString()
}

export function formatNumber(value: unknown, digits = 2): string {
  if (value == null || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(digits)
}

export function getResearchStatusMeta(
  status: string | null | undefined,
  isZh: boolean
): { label: string; className: string } {
  switch (status) {
    case 'running':
      return {
        label: isZh ? '运行中' : 'Running',
        className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600',
      }
    case 'success':
      return {
        label: isZh ? '已完成' : 'Completed',
        className: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-600',
      }
    case 'error':
      return {
        label: isZh ? '错误' : 'Error',
        className: 'border-red-500/30 bg-red-500/10 text-red-600',
      }
    default:
      return {
        label: isZh ? '空闲' : 'Idle',
        className: 'border-muted bg-muted/40 text-muted-foreground',
      }
  }
}

export function getViewTitle(view: FactorPipelineView, isZh: boolean): string {
  if (view === 'deployments') return isZh ? '组合部署记录' : 'Portfolio Deployments'
  if (view === 'live-gate') return isZh ? '实盘门控状态' : 'Live Gate Status'
  return isZh ? '因子研究中心' : 'Factor Research Workspace'
}

export function getViewDescription(view: FactorPipelineView, isZh: boolean): string {
  if (view === 'deployments') {
    return isZh
      ? '查看最优组合部署，并执行纸面/实盘绑定。'
      : 'Review portfolio deployments and trigger paper/live bindings.'
  }
  if (view === 'live-gate') {
    return isZh
      ? '查看实盘提升门控检查结果与最新决策。'
      : 'Inspect live promotion gate checks and latest decision.'
  }
  return isZh
    ? '执行因子生成、组合筛选与分阶段回测。'
    : 'Run factor generation, portfolio selection, and staged backtests.'
}
