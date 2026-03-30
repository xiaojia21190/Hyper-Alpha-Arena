import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  getLatestFactorPortfolioRun,
  getLatestLiveGateStatus,
  triggerFactorResearchRun,
} from '@/lib/api'
import { BarChart3, Play, RefreshCw } from 'lucide-react'
import FactorDeploymentsStage from './pipeline/FactorDeploymentsStage'
import FactorLiveGateStage from './pipeline/FactorLiveGateStage'
import FactorResearchStage from './pipeline/FactorResearchStage'
import {
  getResearchStatusMeta,
  getViewDescription,
  getViewTitle,
  type FactorPipelineView,
} from './pipeline/shared'

export type { FactorPipelineView }

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
const RESEARCH_ACTIVE_POLL_INTERVAL_MS = 10000
const DEPLOYMENT_POLL_INTERVAL_MS = 15000

const LIVE_CHECK_LABELS: Record<string, { en: string; zh: string }> = {
  observation_hours: { en: 'Observation hours', zh: '观察时长' },
  trade_count: { en: 'Trade count', zh: '交易数' },
  net_pnl: { en: 'Net PnL', zh: '净收益' },
  win_rate_percent: { en: 'Win rate %', zh: '胜率' },
  max_drawdown_percent: { en: 'Max drawdown %', zh: '最大回撤' },
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
    void loadResearchStatus(true)
    void loadPortfolioSnapshot()
    void loadLiveGateSnapshot()
    void loadDeployments()
    void loadDeployAccounts()
  }, [loadDeployAccounts, loadDeployments, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus])

  useEffect(() => {
    const intervalMs = researchStatus?.status === 'running'
      ? RESEARCH_ACTIVE_POLL_INTERVAL_MS
      : RESEARCH_POLL_INTERVAL_MS
    const timer = window.setInterval(() => {
      void loadResearchStatus()
    }, intervalMs)
    return () => window.clearInterval(timer)
  }, [loadResearchStatus, researchStatus?.status])

  useEffect(() => {
    if (view !== 'deployments') return
    const timer = window.setInterval(() => {
      void loadDeployments()
    }, DEPLOYMENT_POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [loadDeployments, view])

  useEffect(() => {
    if (view !== 'live-gate') return
    const timer = window.setInterval(() => {
      void loadLiveGateSnapshot()
    }, RESEARCH_POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [loadLiveGateSnapshot, view])

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
  }, [isZh, liveDecision?.gate?.checks])

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

  const refreshAll = useCallback(() => {
    void loadResearchStatus(true)
    void loadPortfolioSnapshot()
    void loadLiveGateSnapshot()
    void loadDeployments()
  }, [loadDeployments, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus])

  const stageContent = (() => {
    if (view === 'research') {
      return (
        <FactorResearchStage
          isZh={isZh}
          researchConfig={researchConfig}
          researchLoopHours={researchLoopHours}
          researchStatus={researchStatus}
          researchIsRunning={researchIsRunning}
          researchProgress={researchProgress}
          researchProgressPercent={researchProgressPercent}
          researchTopFactor={researchTopFactor}
          researchLeaderboard={researchLeaderboard}
        />
      )
    }

    if (view === 'deployments') {
      return (
        <FactorDeploymentsStage
          isZh={isZh}
          topPortfolio={topPortfolio}
          topPortfolioId={topPortfolioId}
          portfolioLoading={portfolioLoading}
          availableAccounts={availableAccounts}
          deployAccountId={deployAccountId}
          onDeployAccountChange={setDeployAccountId}
          portfolioActionLoading={portfolioActionLoading}
          portfolioActionError={portfolioActionError}
          portfolioActionSuccess={portfolioActionSuccess}
          portfolioLeaderboard={portfolioLeaderboard}
          deployments={deployments}
          deploymentsLoading={deploymentsLoading}
          onDeployPortfolioPaper={handleDeployPortfolioPaper}
          onDeployPortfolioLive={handleDeployPortfolioLive}
        />
      )
    }

    return (
      <FactorLiveGateStage
        isZh={isZh}
        latestRunMeta={latestRunMeta}
        decisionRunMeta={decisionRunMeta}
        liveDecision={liveDecision}
        liveChecks={liveChecks}
        lastRunError={researchStatus?.last_error}
      />
    )
  })()

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
              onClick={refreshAll}
            >
              <RefreshCw className={`mr-1 h-3.5 w-3.5 ${researchStatusLoading ? 'animate-spin' : ''}`} />
              {isZh ? '刷新' : 'Refresh'}
            </Button>
            {view === 'research' && (
              <Button size="sm" onClick={handleResearchRun} disabled={researchStarting || researchIsRunning}>
                {researchStarting || researchIsRunning
                  ? <RefreshCw className="mr-1 h-3.5 w-3.5 animate-spin" />
                  : <Play className="mr-1 h-3.5 w-3.5" />}
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

      {stageContent}
    </div>
  )
}
