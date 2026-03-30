import { Badge } from '@/components/ui/badge'
import { Clock3, Trophy } from 'lucide-react'
import type {
  FactorResearchProgress,
  FactorResearchRankedResult,
  FactorResearchRunConfig,
  FactorResearchStatus,
} from '@/lib/api'
import { formatNumber, formatTimestamp } from './shared'

interface FactorResearchStageProps {
  isZh: boolean
  researchConfig: FactorResearchRunConfig
  researchLoopHours: string
  researchStatus: FactorResearchStatus | null
  researchIsRunning: boolean
  researchProgress: FactorResearchProgress | null
  researchProgressPercent: number | null
  researchTopFactor: FactorResearchRankedResult | null
  researchLeaderboard: FactorResearchRankedResult[]
}

export default function FactorResearchStage({
  isZh,
  researchConfig,
  researchLoopHours,
  researchStatus,
  researchIsRunning,
  researchProgress,
  researchProgressPercent,
  researchTopFactor,
  researchLeaderboard,
}: FactorResearchStageProps) {
  return (
    <>
      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">{isZh ? '研究范围' : 'Research scope'}</div>
          <div className="mt-1 text-sm font-medium">
            Top {researchConfig.top_n_symbols} / {researchConfig.lookback_days}d / {researchConfig.period}
          </div>
        </div>
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">{isZh ? '循环间隔' : 'Loop interval'}</div>
          <div className="mt-1 text-sm font-medium">{researchLoopHours}h</div>
        </div>
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock3 className="h-3 w-3" />
            {isZh ? '最近启动' : 'Last started'}
          </div>
          <div className="mt-1 text-sm font-medium">{formatTimestamp(researchStatus?.last_run_started_at)}</div>
        </div>
        <div className="rounded-lg border bg-background/70 p-3">
          <div className="text-xs text-muted-foreground">{isZh ? '最近完成' : 'Last completed'}</div>
          <div className="mt-1 text-sm font-medium">{formatTimestamp(researchStatus?.last_run_completed_at)}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {researchStatus?.last_result?.candidate_count ?? 0} {isZh ? '个候选因子' : 'candidates'}
          </div>
        </div>
      </div>

      {researchIsRunning && researchProgress && (
        <div className="rounded-lg border bg-background/80 p-4 space-y-3">
          <div className="text-sm font-semibold">{isZh ? '当前进度' : 'Current progress'}</div>
          {researchProgressPercent != null && (
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-2 bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all"
                style={{ width: `${researchProgressPercent}%` }}
              />
            </div>
          )}
          <div className="grid gap-3 text-sm md:grid-cols-3">
            <div className="rounded-lg border bg-background/70 p-3">
              <div className="text-xs text-muted-foreground">{isZh ? '当前阶段' : 'Phase'}</div>
              <div className="mt-1 font-medium">{researchProgress.phase || '--'}</div>
            </div>
            <div className="rounded-lg border bg-background/70 p-3">
              <div className="text-xs text-muted-foreground">{isZh ? '当前因子' : 'Current factor'}</div>
              <div className="mt-1 break-all font-medium font-mono">{researchProgress.current_factor || '--'}</div>
            </div>
            <div className="rounded-lg border bg-background/70 p-3">
              <div className="text-xs text-muted-foreground">{isZh ? '进度' : 'Progress'}</div>
              <div className="mt-1 font-medium font-mono">
                {researchProgress.current ?? '--'} / {researchProgress.total ?? '--'}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-lg border bg-background/80 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Trophy className="h-4 w-4 text-amber-500" />
            <div className="text-sm font-semibold">{isZh ? '最优因子' : 'Top factor'}</div>
          </div>
          {researchTopFactor ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <div className="text-xs text-muted-foreground">{isZh ? '因子' : 'Factor'}</div>
                <div className="mt-1 font-medium font-mono">{researchTopFactor.factor_name}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Score</div>
                <div className="mt-1 font-medium font-mono">{formatNumber(researchTopFactor.score, 4)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{isZh ? '收益' : 'Return %'}</div>
                <div className="mt-1 font-medium font-mono text-emerald-600">
                  {formatNumber(researchTopFactor.total_pnl_percent, 2)}%
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{isZh ? '回撤' : 'Drawdown %'}</div>
                <div className="mt-1 font-medium font-mono text-red-500">
                  {formatNumber(researchTopFactor.max_drawdown_percent, 2)}%
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              {isZh ? '暂无已完成研究结果。' : 'No completed research result yet.'}
            </div>
          )}
        </div>

        <div className="rounded-lg border bg-background/80 p-4 space-y-3">
          <div className="text-sm font-semibold">{isZh ? '最近排行榜' : 'Latest leaderboard'}</div>
          {researchLeaderboard.length > 0 ? (
            <div className="space-y-2">
              {researchLeaderboard.map((row, index) => (
                <div
                  key={`${row.factor_name}-${index}`}
                  className="flex flex-wrap items-center gap-2 rounded-lg border bg-background/70 px-3 py-2 text-sm"
                >
                  <Badge variant="outline" className="font-mono">
                    #{index + 1}
                  </Badge>
                  <span className="min-w-[130px] font-medium">{row.factor_name}</span>
                  <span className="font-mono text-muted-foreground">
                    score {formatNumber(row.score, 4)}
                  </span>
                  <span className="font-mono text-emerald-600">
                    pnl {formatNumber(row.total_pnl_percent, 2)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              {isZh ? '暂无排行榜数据。' : 'No leaderboard data yet.'}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
