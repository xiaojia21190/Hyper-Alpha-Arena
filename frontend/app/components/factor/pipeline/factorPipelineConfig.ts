import type { FactorResearchRunConfig } from '@/lib/api'

export const DEFAULT_RESEARCH_RUN_CONFIG: FactorResearchRunConfig = {
  exchange: 'hyperliquid',
  top_n_symbols: 20,
  lookback_days: 180,
  objective: 'return_over_drawdown',
  factor_scope: 'builtin_only',
  period: '1h',
  prescreen_limit: 10,
}

export const RESEARCH_POLL_INTERVAL_MS = 15000
export const RESEARCH_ACTIVE_POLL_INTERVAL_MS = 10000
export const DEPLOYMENT_POLL_INTERVAL_MS = 15000

export const LIVE_CHECK_LABELS: Record<string, { en: string; zh: string }> = {
  observation_hours: { en: 'Observation hours', zh: '\u89c2\u5bdf\u65f6\u957f' },
  trade_count: { en: 'Trade count', zh: '\u4ea4\u6613\u6570' },
  net_pnl: { en: 'Net PnL', zh: '\u51c0\u6536\u76ca' },
  win_rate_percent: { en: 'Win rate %', zh: '\u80dc\u7387' },
  max_drawdown_percent: { en: 'Max drawdown %', zh: '\u6700\u5927\u56de\u64a4' },
}

export const pickFactorPipelineMessage = (isZh: boolean, zh: string, en: string) => (
  isZh ? zh : en
)
