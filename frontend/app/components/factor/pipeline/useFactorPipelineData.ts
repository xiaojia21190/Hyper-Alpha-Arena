import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  type FactorLiveDecision,
  type FactorLiveGateSnapshot,
  type FactorPortfolioCandidate,
  type FactorPortfolioDeploymentRecord,
  type FactorResearchProgress,
  type FactorResearchStatus,
  getAccounts,
  getFactorPortfolioDeployments,
  getFactorResearchStatus,
  getLatestFactorPortfolioRun,
  getLatestLiveGateStatus,
} from '@/lib/api'
import { getResearchStatusMeta, type FactorPipelineView } from './shared'
import {
  DEFAULT_RESEARCH_RUN_CONFIG,
  DEPLOYMENT_POLL_INTERVAL_MS,
  LIVE_CHECK_LABELS,
  RESEARCH_ACTIVE_POLL_INTERVAL_MS,
  RESEARCH_POLL_INTERVAL_MS,
  pickFactorPipelineMessage,
} from './factorPipelineConfig'
import { useFactorPipelineActions } from './useFactorPipelineActions'

type AccountOption = {
  id: number
  name: string
}

export function useFactorPipelineData(view: FactorPipelineView, isZh: boolean) {
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

  const [availableAccounts, setAvailableAccounts] = useState<AccountOption[]>([])
  const [deployAccountId, setDeployAccountId] = useState(0)
  const [liveGateSnapshot, setLiveGateSnapshot] = useState<FactorLiveGateSnapshot | null>(null)

  const loadResearchStatus = useCallback(async (showLoader = false) => {
    if (statusRequestInFlightRef.current) return
    statusRequestInFlightRef.current = true
    if (showLoader) setResearchStatusLoading(true)
    try {
      const payload = await getFactorResearchStatus()
      setResearchStatus(payload)
      setStatusError('')
    } catch (error: any) {
      setStatusError(
        error?.message
          || pickFactorPipelineMessage(isZh, '\u8bfb\u53d6\u7814\u7a76\u72b6\u6001\u5931\u8d25', 'Failed to load research status')
      )
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
      setDeployAccountId((previousValue) => {
        if (previousValue > 0) return previousValue
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

  const topPortfolio = (
    researchStatus?.last_result?.top_portfolio
    || researchStatus?.last_top_portfolio
    || portfolioSnapshot?.top_portfolio
    || null
  ) as FactorPortfolioCandidate | null
  const topPortfolioId = Number(topPortfolio?.portfolio_id || topPortfolio?.id || 0)
  const portfolioLeaderboard = (
    researchStatus?.last_result?.portfolio_ranked_results
    || portfolioSnapshot?.portfolio_candidates
    || []
  ).slice(0, 10) as FactorPortfolioCandidate[]

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

  const refreshAll = useCallback(() => {
    void loadResearchStatus(true)
    void loadPortfolioSnapshot()
    void loadLiveGateSnapshot()
    void loadDeployments()
  }, [loadDeployments, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus])

  const {
    handleDeployPortfolioLive,
    handleDeployPortfolioPaper,
    handleResearchRun,
  } = useFactorPipelineActions({
    deployAccountId,
    isZh,
    loadDeployments,
    loadLiveGateSnapshot,
    loadPortfolioSnapshot,
    loadResearchStatus,
    researchStatus,
    setPortfolioActionError,
    setPortfolioActionLoading,
    setPortfolioActionSuccess,
    setResearchStarting,
    setResearchStatus,
    setStatusError,
    setStatusNotice,
    topPortfolioId,
  })

  return {
    availableAccounts,
    decisionRunMeta,
    deployAccountId,
    deployments,
    deploymentsLoading,
    handleDeployPortfolioLive,
    handleDeployPortfolioPaper,
    handleResearchRun,
    latestRunMeta,
    liveChecks,
    liveDecision,
    portfolioActionError,
    portfolioActionLoading,
    portfolioActionSuccess,
    portfolioLeaderboard,
    portfolioLoading,
    refreshAll,
    researchConfig,
    researchIsRunning,
    researchLeaderboard,
    researchLoopHours,
    researchProgress,
    researchProgressPercent,
    researchStarting,
    researchStateMeta,
    researchStatus,
    researchStatusLoading,
    researchTopFactor,
    setDeployAccountId,
    statusError,
    statusNotice,
    topPortfolio,
    topPortfolioId,
  }
}
