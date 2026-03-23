import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  type FactorLiveDecision,
  type FactorLiveGateSnapshot,
  type FactorPortfolioCandidate,
  type FactorPortfolioDeploymentRecord,
  type FactorResearchProgress,
  type FactorResearchRunConfig,
  type FactorResearchStatus,
  deployFactorPortfolioLive,
  deployFactorPortfolioPaper,
  getAccounts,
  getFactorPortfolioDeployments,
  getFactorResearchStatus,
  getLatestLiveGateStatus,
  getLatestFactorPortfolioRun,
  triggerFactorResearchRun,
} from '@/lib/api'
import { BarChart3, Clock3, Play, RefreshCw, Rocket, ShieldAlert, Trophy } from 'lucide-react'

export type FactorPipelineView = 'research' | 'deployments' | 'live-gate'

const DEFAULT_RESEARCH_RUN_CONFIG: FactorResearchRunConfig = {
  exchange: 'hyperliquid',
  top_n_symbols: 20,
  lookback_days: 180,
  objective: 'return_over_drawdown',
  factor_scope: 'builtin_only',
  period: '1h',
  prescreen_limit: 10,
}

const RESEARCH_POLL_INTERVAL_MS = 15000
const RESEARCH_ACTIVE_POLL_INTERVAL_MS = 5000
const DEPLOYMENT_POLL_INTERVAL_MS = 15000

const LIVE_CHECK_LABELS: Record<string, { en: string; zh: string }> = {
  observation_hours: { en: 'Observation hours', zh: '观察时长' },
  trade_count: { en: 'Trade count', zh: '交易数' },
  net_pnl: { en: 'Net PnL', zh: '净收益' },
  win_rate_percent: { en: 'Win rate %', zh: '胜率' },
  max_drawdown_percent: { en: 'Max drawdown %', zh: '最大回撤' },
}

function formatTimestamp(ts: number | null | undefined): string {
  if (!ts) return '--'
  return new Date(ts * 1000).toLocaleString()
}

function formatIso(ts: string | null | undefined): string {
  if (!ts) return '--'
  return new Date(ts).toLocaleString()
}

function formatNumber(value: unknown, digits = 2): string {
  if (value == null || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(digits)
}

function getResearchStatusMeta(status: string | null | undefined, isZh: boolean): {
  label: string
  className: string
} {
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

function getViewTitle(view: FactorPipelineView, isZh: boolean): string {
  if (view === 'deployments') return isZh ? '组合部署记录' : 'Portfolio Deployments'
  if (view === 'live-gate') return isZh ? '实盘门控状态' : 'Live Gate Status'
  return isZh ? '因子研究中心' : 'Factor Research Workspace'
}

function getViewDescription(view: FactorPipelineView, isZh: boolean): string {
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

export default function FactorPipelineWorkspace({ view }: { view: FactorPipelineView }) {
  const { i18n } = useTranslation()
  const isZh = i18n.language?.startsWith('zh')

  const [researchStatus, setResearchStatus] = useState<FactorResearchStatus | null>(null)
  const [researchStatusLoading, setResearchStatusLoading] = useState(true)
  const [researchStarting, setResearchStarting] = useState(false)
  const [statusError, setStatusError] = useState('')
  const [statusNotice, setStatusNotice] = useState('')
  const statusRequestInFlightRef = useRef(false)

  const [portfolioSnapshot, setPortfolioSnapshot] = useState<{
    portfolio_candidates: FactorPortfolioCandidate[]
    top_portfolio: FactorPortfolioCandidate | null
  } | null>(null)
  const [portfolioLoading, setPortfolioLoading] = useState(false)

  const [deployments, setDeployments] = useState<FactorPortfolioDeploymentRecord[]>([])
  const [deploymentsLoading, setDeploymentsLoading] = useState(false)

  const [portfolioActionLoading, setPortfolioActionLoading] = useState<'paper' | 'live' | null>(null)
  const [portfolioActionError, setPortfolioActionError] = useState('')
  const [portfolioActionSuccess, setPortfolioActionSuccess] = useState('')

  const [availableAccounts, setAvailableAccounts] = useState<Array<{ id: number; name: string }>>([])
  const [deployAccountId, setDeployAccountId] = useState<number>(0)
  const [liveGateSnapshot, setLiveGateSnapshot] = useState<FactorLiveGateSnapshot | null>(null)

  const loadResearchStatus = useCallback(async (showLoader = false) => {
    if (statusRequestInFlightRef.current) return
    statusRequestInFlightRef.current = true
    if (showLoader) setResearchStatusLoading(true)
    try {
      const payload = await getFactorResearchStatus()
      setResearchStatus(payload)
      setStatusError('')
    } catch (e: any) {
      setStatusError(e?.message || (isZh ? '读取研究状态失败' : 'Failed to load research status'))
    } finally {
      statusRequestInFlightRef.current = false
      if (showLoader) setResearchStatusLoading(false)
    }
  }, [isZh])

  const loadPortfolioSnapshot = useCallback(async () => {
    setPortfolioLoading(true)
    try {
      const payload = await getLatestFactorPortfolioRun()
      setPortfolioSnapshot(payload)
    } catch {
      setPortfolioSnapshot(null)
    } finally {
      setPortfolioLoading(false)
    }
  }, [])

  const loadLiveGateSnapshot = useCallback(async () => {
    try {
      const payload = await getLatestLiveGateStatus()
      setLiveGateSnapshot(payload)
    } catch {
      setLiveGateSnapshot(null)
    }
  }, [])

  const loadDeployments = useCallback(async () => {
    setDeploymentsLoading(true)
    try {
      const payload = await getFactorPortfolioDeployments({ limit: 50 })
      setDeployments(payload.items || [])
    } catch {
      setDeployments([])
    } finally {
      setDeploymentsLoading(false)
    }
  }, [])

  const loadDeployAccounts = useCallback(async () => {
    try {
      const rows = await getAccounts({ include_hidden: true })
      const activeRows = (rows || [])
        .filter((row) => row.is_active)
        .map((row) => ({
          id: row.id,
          name: row.name || `Account ${row.id}`,
        }))
      setAvailableAccounts(activeRows)
      setDeployAccountId((prev) => {
        if (prev > 0) return prev
        return activeRows[0]?.id || 0
      })
    } catch {
      setAvailableAccounts([])
    }
  }, [])

  useEffect(() => {
    loadResearchStatus(true)
    loadPortfolioSnapshot()
    loadLiveGateSnapshot()
    loadDeployments()
    loadDeployAccounts()
  }, [loadResearchStatus, loadPortfolioSnapshot, loadLiveGateSnapshot, loadDeployments, loadDeployAccounts])

  useEffect(() => {
    const intervalMs = researchStatus?.status === 'running'
      ? RESEARCH_ACTIVE_POLL_INTERVAL_MS
      : RESEARCH_POLL_INTERVAL_MS
    const timer = window.setInterval(() => {
      loadResearchStatus()
    }, intervalMs)
    return () => window.clearInterval(timer)
  }, [loadResearchStatus, researchStatus?.status])

  useEffect(() => {
    if (view !== 'deployments') return
    const timer = window.setInterval(() => {
      loadDeployments()
    }, DEPLOYMENT_POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [view, loadDeployments])

  useEffect(() => {
    if (view !== 'live-gate') return
    const timer = window.setInterval(() => {
      loadLiveGateSnapshot()
    }, RESEARCH_POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [view, loadLiveGateSnapshot])

  const researchState = researchStatus?.status === 'running'
    ? 'running'
    : (researchStatus?.last_run_status || 'idle')
  const researchStateMeta = getResearchStatusMeta(researchState, isZh)
  const researchConfig = researchStatus?.config || DEFAULT_RESEARCH_RUN_CONFIG
  const researchIsRunning = researchStatus?.status === 'running'
  const researchProgress = researchStatus?.progress as FactorResearchProgress | null
  const researchTopFactor = researchStatus?.last_top_factor
  const researchLeaderboard = researchStatus?.last_result?.ranked_results?.slice(0, 5) || []

  const topPortfolio: FactorPortfolioCandidate | null = (
    researchStatus?.last_result?.top_portfolio
    || researchStatus?.last_top_portfolio
    || portfolioSnapshot?.top_portfolio
    || null
  ) as FactorPortfolioCandidate | null
  const topPortfolioId = Number(topPortfolio?.portfolio_id || topPortfolio?.id || 0)
  const portfolioLeaderboard: FactorPortfolioCandidate[] = (
    researchStatus?.last_result?.portfolio_ranked_results
    || portfolioSnapshot?.portfolio_candidates
    || []
  ).slice(0, 10)

  const researchLoopHours = researchStatus?.interval_seconds
    ? (researchStatus.interval_seconds / 3600).toFixed(researchStatus.interval_seconds % 3600 === 0 ? 0 : 1)
    : '--'

  const researchProgressPercent = researchProgress?.total && researchProgress.total > 0
    ? Math.max(0, Math.min(100, Math.round(((researchProgress.current || 0) / researchProgress.total) * 100)))
    : null

  const inMemoryLiveDecision = (researchStatus?.last_result as any)?.auto_live_decision as FactorLiveDecision | null | undefined
  const liveDecision = inMemoryLiveDecision || liveGateSnapshot?.live_decision || null
  const latestRunMeta = (liveGateSnapshot?.latest_run || null) as Record<string, any> | null
  const decisionRunMeta = (liveGateSnapshot?.decision_run || null) as Record<string, any> | null

  const liveChecks = useMemo(() => {
    const checks = liveDecision?.gate?.checks || {}
    return Object.entries(checks).map(([key, payload]) => ({
      key,
      label: (LIVE_CHECK_LABELS[key] || { en: key, zh: key })[isZh ? 'zh' : 'en'],
      actual: payload?.actual,
      threshold: payload?.threshold,
      passed: Boolean(payload?.passed),
    }))
  }, [liveDecision?.gate?.checks, isZh])

  const handleResearchRun = useCallback(async () => {
    setResearchStarting(true)
    setStatusError('')
    setStatusNotice('')
    try {
      const config: FactorResearchRunConfig = {
        ...DEFAULT_RESEARCH_RUN_CONFIG,
        ...(researchStatus?.config || {}),
      }
      const response = await triggerFactorResearchRun(config)
      if (response.status === 'already_running') {
        setStatusNotice(isZh ? '研究任务已在后台运行' : 'Research run is already running in the background')
        setResearchStatus((prev) => (prev ? { ...prev, status: 'running' } : prev))
      } else {
        const now = Math.floor(Date.now() / 1000)
        setStatusNotice(isZh ? '已触发研究，结果将稍后刷新' : 'Research run started. Results will refresh shortly.')
        setResearchStatus((prev) => {
          if (!prev) {
            return {
              enabled: false,
              status: 'running',
              interval_seconds: null,
              config,
              last_run_status: 'running',
              last_run_started_at: now,
              last_run_completed_at: null,
              last_error: null,
              last_top_factor: null,
              last_top_portfolio: null,
              last_result: null,
              progress: {
                phase: 'queued',
                current: 0,
                total: 0,
                updated_at: now,
              },
            }
          }
          return {
            ...prev,
            status: 'running',
            last_run_status: 'running',
            last_run_started_at: now,
            last_error: null,
          }
        })
      }
      void loadResearchStatus(true)
      void loadLiveGateSnapshot()
      void loadPortfolioSnapshot()
    } catch (e: any) {
      setStatusNotice('')
      setStatusError(e?.message || (isZh ? '启动研究失败' : 'Failed to start research'))
    } finally {
      setResearchStarting(false)
    }
  }, [isZh, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus, researchStatus?.config])

  const handleDeployPortfolioPaper = useCallback(async () => {
    if (!topPortfolioId) return
    if (!deployAccountId || deployAccountId <= 0) {
      setPortfolioActionError(isZh ? '请选择有效账户' : 'Please choose a valid account')
      return
    }
    setPortfolioActionLoading('paper')
    setPortfolioActionError('')
    setPortfolioActionSuccess('')
    try {
      const payload = await deployFactorPortfolioPaper(topPortfolioId, {
        account_id: deployAccountId,
        period: '1h',
        trigger_interval: 3600,
        signal_pool_ids: [],
        exchange: 'hyperliquid',
      })
      setPortfolioActionSuccess(
        isZh
          ? `纸面部署成功：Program #${payload.program.id}，Binding #${payload.binding.id}`
          : `Paper deployment succeeded: Program #${payload.program.id}, Binding #${payload.binding.id}`
      )
      await Promise.all([loadResearchStatus(), loadPortfolioSnapshot(), loadLiveGateSnapshot(), loadDeployments()])
    } catch (e: any) {
      setPortfolioActionError(e?.message || (isZh ? '纸面部署失败' : 'Paper deployment failed'))
    } finally {
      setPortfolioActionLoading(null)
    }
  }, [deployAccountId, isZh, loadDeployments, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus, topPortfolioId])

  const handleDeployPortfolioLive = useCallback(async () => {
    if (!topPortfolioId) return
    if (!deployAccountId || deployAccountId <= 0) {
      setPortfolioActionError(isZh ? '请选择有效账户' : 'Please choose a valid account')
      return
    }
    const confirmed = window.confirm(
      isZh
        ? '确认执行实盘部署？这会创建可执行实盘绑定。'
        : 'Confirm live deployment? This will create an executable live binding.'
    )
    if (!confirmed) return

    setPortfolioActionLoading('live')
    setPortfolioActionError('')
    setPortfolioActionSuccess('')
    try {
      const payload = await deployFactorPortfolioLive(topPortfolioId, {
        account_id: deployAccountId,
        confirm_live: true,
        period: '1h',
        trigger_interval: 3600,
        signal_pool_ids: [],
        exchange: 'hyperliquid',
      })
      setPortfolioActionSuccess(
        isZh
          ? `实盘部署成功：Program #${payload.program.id}，Binding #${payload.binding.id}`
          : `Live deployment succeeded: Program #${payload.program.id}, Binding #${payload.binding.id}`
      )
      await Promise.all([loadResearchStatus(), loadPortfolioSnapshot(), loadLiveGateSnapshot(), loadDeployments()])
    } catch (e: any) {
      setPortfolioActionError(e?.message || (isZh ? '实盘部署失败' : 'Live deployment failed'))
    } finally {
      setPortfolioActionLoading(null)
    }
  }, [deployAccountId, isZh, loadDeployments, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus, topPortfolioId])

  return (
    <div className="flex flex-col flex-1 min-h-0 space-y-4">
      <div className="rounded-xl border bg-background/70 px-4 py-3">
        <div className="flex flex-wrap items-start gap-3">
          <div>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-emerald-500" />
              <h2 className="text-sm font-semibold">{getViewTitle(view, isZh)}</h2>
              <Badge variant="outline" className={researchStateMeta.className}>
                {researchStateMeta.label}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{getViewDescription(view, isZh)}</p>
          </div>

          <div className="ml-auto flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={researchStatusLoading}
              onClick={() => {
                loadResearchStatus(true)
                loadPortfolioSnapshot()
                loadLiveGateSnapshot()
                loadDeployments()
              }}
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1 ${researchStatusLoading ? 'animate-spin' : ''}`} />
              {isZh ? '刷新' : 'Refresh'}
            </Button>
            {view === 'research' && (
              <Button size="sm" onClick={handleResearchRun} disabled={researchStarting || researchIsRunning}>
                {researchStarting || researchIsRunning
                  ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" />
                  : <Play className="h-3.5 w-3.5 mr-1" />}
                {researchIsRunning
                  ? (isZh ? '研究运行中' : 'Research running')
                  : (isZh ? '运行一次' : 'Run once')}
              </Button>
            )}
          </div>
        </div>
      </div>

      {statusError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-500">
          {statusError}
        </div>
      )}
      {statusNotice && (
        <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-700">
          {statusNotice}
        </div>
      )}

      {view === 'research' && (
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
                <div className="w-full rounded-full bg-muted h-2 overflow-hidden">
                  <div
                    className="h-2 bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all"
                    style={{ width: `${researchProgressPercent}%` }}
                  />
                </div>
              )}
              <div className="grid gap-3 md:grid-cols-3 text-sm">
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '当前阶段' : 'Phase'}</div>
                  <div className="mt-1 font-medium">{researchProgress.phase || '--'}</div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '当前因子' : 'Current factor'}</div>
                  <div className="mt-1 font-medium font-mono break-all">{researchProgress.current_factor || '--'}</div>
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
                    <div key={`${row.factor_name}-${index}`} className="flex flex-wrap items-center gap-2 rounded-lg border bg-background/70 px-3 py-2 text-sm">
                      <Badge variant="outline" className="font-mono">#{index + 1}</Badge>
                      <span className="font-medium min-w-[130px]">{row.factor_name}</span>
                      <span className="font-mono text-muted-foreground">score {formatNumber(row.score, 4)}</span>
                      <span className="font-mono text-emerald-600">pnl {formatNumber(row.total_pnl_percent, 2)}%</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">{isZh ? '暂无排行榜数据。' : 'No leaderboard data yet.'}</div>
              )}
            </div>
          </div>
        </>
      )}

      {view === 'deployments' && (
        <>
          <div className="rounded-lg border bg-background/80 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Rocket className="h-4 w-4 text-indigo-500" />
              <div className="text-sm font-semibold">{isZh ? '最优组合部署' : 'Top portfolio deployment'}</div>
              {portfolioLoading && (
                <Badge variant="outline" className="text-xs">
                  {isZh ? '加载中' : 'Loading'}
                </Badge>
              )}
            </div>

            {topPortfolio ? (
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">{isZh ? '组合名称' : 'Portfolio'}</div>
                  <div className="mt-1 text-sm font-semibold break-all">{topPortfolio.name}</div>
                  <div className="mt-1 text-xs text-muted-foreground font-mono">{topPortfolio.construction_method}</div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <div className="text-xs text-muted-foreground">Score</div>
                  <div className="mt-1 text-sm font-semibold font-mono">{formatNumber(topPortfolio.score, 4)}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {isZh ? '组件数' : 'Components'}: {topPortfolio.component_count ?? topPortfolio.weights?.length ?? 0}
                  </div>
                </div>
                <div className="rounded-lg border bg-background/70 p-3 space-y-2">
                  <div className="text-xs text-muted-foreground">{isZh ? '部署账户' : 'Deploy account'}</div>
                  {availableAccounts.length > 0 ? (
                    <Select value={String(deployAccountId || availableAccounts[0].id)} onValueChange={(value) => setDeployAccountId(Number(value))}>
                      <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {availableAccounts.map((row) => (
                          <SelectItem key={row.id} value={String(row.id)}>
                            {row.name} (#{row.id})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type="number"
                      min={1}
                      value={deployAccountId || 0}
                      onChange={(e) => setDeployAccountId(Number(e.target.value || 0))}
                      className="h-8"
                    />
                  )}
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">
                {isZh ? '暂无可部署组合，请先完成研究。' : 'No deployable portfolio yet. Complete a research run first.'}
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={!topPortfolioId || portfolioActionLoading !== null} onClick={handleDeployPortfolioPaper}>
                {portfolioActionLoading === 'paper'
                  ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" />
                  : <Play className="h-3.5 w-3.5 mr-1" />}
                {isZh ? '部署到纸面' : 'Deploy to paper'}
              </Button>
              <Button size="sm" variant="outline" disabled={!topPortfolioId || portfolioActionLoading !== null} onClick={handleDeployPortfolioLive}>
                {portfolioActionLoading === 'live'
                  ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" />
                  : <Rocket className="h-3.5 w-3.5 mr-1" />}
                {isZh ? '部署到实盘' : 'Deploy to live'}
              </Button>
            </div>

            {portfolioActionError && (
              <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-500">
                {portfolioActionError}
              </div>
            )}
            {portfolioActionSuccess && (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-600">
                {portfolioActionSuccess}
              </div>
            )}
          </div>

          {portfolioLeaderboard.length > 0 && (
            <div className="rounded-lg border bg-background/80 p-4 space-y-3">
              <div className="text-sm font-semibold">{isZh ? '组合排行榜' : 'Portfolio leaderboard'}</div>
              <div className="grid gap-2">
                {portfolioLeaderboard.map((row, index) => (
                  <div key={`${row.name}-${index}`} className="flex flex-wrap items-center gap-3 rounded-lg border bg-background/70 px-3 py-2 text-sm">
                    <Badge variant="outline" className="font-mono">#{index + 1}</Badge>
                    <span className="font-medium min-w-[130px]">{row.name}</span>
                    <span className="font-mono text-muted-foreground">score {formatNumber(row.score, 4)}</span>
                    <span className="font-mono text-muted-foreground">{row.construction_method}</span>
                    <span className="font-mono text-muted-foreground">
                      {isZh ? '组件' : 'components'} {row.component_count ?? row.weights?.length ?? 0}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-lg border bg-background/80 p-4 space-y-3 min-h-0">
            <div className="text-sm font-semibold">{isZh ? '部署历史' : 'Deployment history'}</div>
            <div className="overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{isZh ? '时间' : 'Time'}</TableHead>
                    <TableHead>{isZh ? '模式' : 'Mode'}</TableHead>
                    <TableHead>{isZh ? '状态' : 'Status'}</TableHead>
                    <TableHead>{isZh ? '账户' : 'Account'}</TableHead>
                    <TableHead>Program</TableHead>
                    <TableHead>Binding</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {!deploymentsLoading && deployments.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        {isZh ? '暂无部署记录' : 'No deployment records'}
                      </TableCell>
                    </TableRow>
                  )}
                  {deployments.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{formatIso(row.created_at)}</TableCell>
                      <TableCell className="uppercase">{row.mode || '--'}</TableCell>
                      <TableCell>{row.status || '--'}</TableCell>
                      <TableCell>#{row.account_id}</TableCell>
                      <TableCell>{row.program_id ? `#${row.program_id}` : '--'}</TableCell>
                      <TableCell>{row.binding_id ? `#${row.binding_id}` : '--'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      )}

      {view === 'live-gate' && (
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
                <Badge variant="outline" className="font-mono">{liveDecision.decision || '--'}</Badge>
                {liveDecision.reason && <span className="text-sm text-muted-foreground">{liveDecision.reason}</span>}
              </div>

              {liveDecision.gate && (
                <div className="space-y-2">
                  <div className="text-sm font-semibold">{isZh ? '门控检查' : 'Gate checks'}</div>
                  <div className="grid gap-2">
                    {liveChecks.map((row) => (
                      <div key={row.key} className="flex flex-wrap items-center gap-3 rounded-lg border bg-background/70 px-3 py-2 text-sm">
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
                  <div className="text-sm font-semibold">{isZh ? '纸面观测指标' : 'Paper metrics'}</div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border bg-background/70 p-3">
                      <div className="text-xs text-muted-foreground">{isZh ? '观测时长(h)' : 'Observation (h)'}</div>
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

          {researchStatus?.last_error && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-500">
              <div className="flex items-center gap-1 font-medium">
                <ShieldAlert className="h-3.5 w-3.5" />
                {isZh ? '最近一次运行错误' : 'Last run error'}
              </div>
              <div className="mt-1 break-all">{researchStatus.last_error}</div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
