import { Badge } from '@/components/ui/badge'
import { ShieldAlert } from 'lucide-react'
import type { FactorLiveDecision } from '@/lib/api'
import type { FactorLiveCheckRow } from './shared'
import { formatIso, formatNumber } from './shared'

interface FactorLiveGateStageProps {
  isZh: boolean
  latestRunMeta: Record<string, any> | null
  decisionRunMeta: Record<string, any> | null
  liveDecision: FactorLiveDecision | null
  liveChecks: FactorLiveCheckRow[]
  lastRunError: string | null | undefined
}

export default function FactorLiveGateStage({
  isZh,
  latestRunMeta,
  decisionRunMeta,
  liveDecision,
  liveChecks,
  lastRunError,
}: FactorLiveGateStageProps) {
  return (
    <>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">{isZh ? '最近成功运行' : 'Latest successful run'}</div>
          <div className="mt-1 text-sm font-medium font-mono">#{latestRunMeta?.id ?? '--'}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {formatIso((latestRunMeta?.completed_at as string) || (latestRunMeta?.created_at as string))}
          </div>
        </div>
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">{isZh ? '门控决策来源运行' : 'Decision source run'}</div>
          <div className="mt-1 text-sm font-medium font-mono">#{decisionRunMeta?.id ?? '--'}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {formatIso((decisionRunMeta?.completed_at as string) || (decisionRunMeta?.created_at as string))}
          </div>
        </div>
      </div>

      {!liveDecision ? (
        <div className="rounded-lg border border-dashed bg-background/60 px-4 py-3 text-sm text-muted-foreground">
          {isZh
            ? '暂无实盘门控决策。请先运行一次因子研究并开启 auto_promote_live。'
            : 'No live-gate decision yet. Run factor research with auto_promote_live enabled.'}
        </div>
      ) : (
        <div className="rounded-lg border bg-background/80 p-4 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="font-mono">
              {liveDecision.decision || '--'}
            </Badge>
            {liveDecision.reason && <span className="text-sm text-muted-foreground">{liveDecision.reason}</span>}
          </div>

          {liveDecision.gate && (
            <div className="space-y-2">
              <div className="text-sm font-semibold">{isZh ? '门控检查' : 'Gate checks'}</div>
              <div className="grid gap-2">
                {liveChecks.map((row) => (
                  <div
                    key={row.key}
                    className="flex flex-wrap items-center gap-3 rounded-lg border bg-background/70 px-3 py-2 text-sm"
                  >
                    <span className="min-w-[160px] font-medium">{row.label}</span>
                    <span className="font-mono text-muted-foreground">{formatNumber(row.actual, 4)}</span>
                    <span className="text-muted-foreground">/</span>
                    <span className="font-mono text-muted-foreground">{formatNumber(row.threshold, 4)}</span>
                    <Badge variant="outline" className={row.passed ? 'text-emerald-600' : 'text-red-500'}>
                      {row.passed ? (isZh ? '通过' : 'Passed') : (isZh ? '未通过' : 'Failed')}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {liveDecision.paper_context?.metrics && (
            <div className="space-y-2">
              <div className="text-sm font-semibold">{isZh ? '纸面观察指标' : 'Paper metrics'}</div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '观察时长(h)' : 'Observation (h)'}</div>
                  <div className="mt-1 font-mono">{formatNumber(liveDecision.paper_context.metrics.observation_hours, 2)}</div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '交易数' : 'Trades'}</div>
                  <div className="mt-1 font-mono">{formatNumber(liveDecision.paper_context.metrics.trade_count, 0)}</div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '胜率(%)' : 'Win rate (%)'}</div>
                  <div className="mt-1 font-mono">{formatNumber(liveDecision.paper_context.metrics.win_rate_percent, 2)}</div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '净收益' : 'Net PnL'}</div>
                  <div className="mt-1 font-mono">{formatNumber(liveDecision.paper_context.metrics.net_pnl, 2)}</div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '最大回撤(%)' : 'Max drawdown (%)'}</div>
                  <div className="mt-1 font-mono">{formatNumber(liveDecision.paper_context.metrics.max_drawdown_percent, 2)}</div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '盈利交易数' : 'Winning trades'}</div>
                  <div className="mt-1 font-mono">{formatNumber(liveDecision.paper_context.metrics.winning_trades, 0)}</div>
                </div>
              </div>
            </div>
          )}

          {liveDecision.error && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-500">
              {liveDecision.error}
            </div>
          )}
        </div>
      )}

      {lastRunError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-500">
          <div className="flex items-center gap-1 font-medium">
            <ShieldAlert className="h-3.5 w-3.5" />
            {isZh ? '最近一次运行错误' : 'Last run error'}
          </div>
          <div className="mt-1 break-all">{lastRunError}</div>
        </div>
      )}
    </>
  )
}
