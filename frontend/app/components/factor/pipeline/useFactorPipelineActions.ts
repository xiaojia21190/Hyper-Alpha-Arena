import { useCallback, type Dispatch, type SetStateAction } from 'react'
import {
  type FactorResearchStatus,
  deployFactorPortfolioLive,
  deployFactorPortfolioPaper,
  triggerFactorResearchRun,
} from '@/lib/api'
import {
  DEFAULT_RESEARCH_RUN_CONFIG,
  pickFactorPipelineMessage,
} from './factorPipelineConfig'

type SetString = Dispatch<SetStateAction<string>>
type SetBoolean = Dispatch<SetStateAction<boolean>>
type SetNullableMode = Dispatch<SetStateAction<'paper' | 'live' | null>>
type LoadResearchStatus = (showLoader?: boolean) => Promise<void>
type LoadSimple = () => Promise<void>

type UseFactorPipelineActionsArgs = {
  deployAccountId: number
  isZh: boolean
  loadDeployments: LoadSimple
  loadLiveGateSnapshot: LoadSimple
  loadPortfolioSnapshot: LoadSimple
  loadResearchStatus: LoadResearchStatus
  researchStatus: FactorResearchStatus | null
  setPortfolioActionError: SetString
  setPortfolioActionLoading: SetNullableMode
  setPortfolioActionSuccess: SetString
  setResearchStarting: SetBoolean
  setResearchStatus: Dispatch<SetStateAction<FactorResearchStatus | null>>
  setStatusError: SetString
  setStatusNotice: SetString
  topPortfolioId: number
}

export function useFactorPipelineActions({
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
}: UseFactorPipelineActionsArgs) {
  const handleResearchRun = useCallback(async () => {
    setResearchStarting(true)
    setStatusError('')
    setStatusNotice('')
    try {
      const config = {
        ...DEFAULT_RESEARCH_RUN_CONFIG,
        ...(researchStatus?.config || {}),
      }
      const response = await triggerFactorResearchRun(config)
      if (response.status === 'already_running') {
        setStatusNotice(
          pickFactorPipelineMessage(
            isZh,
            '\u7814\u7a76\u4efb\u52a1\u5df2\u5728\u540e\u53f0\u8fd0\u884c',
            'Research run is already running in the background'
          )
        )
        setResearchStatus((previousValue) => (
          previousValue ? { ...previousValue, status: 'running' } : previousValue
        ))
      } else {
        const now = Math.floor(Date.now() / 1000)
        setStatusNotice(
          pickFactorPipelineMessage(
            isZh,
            '\u5df2\u89e6\u53d1\u7814\u7a76\uff0c\u7ed3\u679c\u5c06\u7a0d\u540e\u5237\u65b0',
            'Research run started. Results will refresh shortly.'
          )
        )
        setResearchStatus((previousValue) => {
          if (!previousValue) {
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
            ...previousValue,
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
    } catch (error: any) {
      setStatusNotice('')
      setStatusError(
        error?.message
          || pickFactorPipelineMessage(isZh, '\u542f\u52a8\u7814\u7a76\u5931\u8d25', 'Failed to start research')
      )
    } finally {
      setResearchStarting(false)
    }
  }, [isZh, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus, researchStatus?.config, setResearchStarting, setResearchStatus, setStatusError, setStatusNotice])

  const handleDeployPortfolioPaper = useCallback(async () => {
    if (!topPortfolioId) return
    if (!deployAccountId || deployAccountId <= 0) {
      setPortfolioActionError(
        pickFactorPipelineMessage(isZh, '\u8bf7\u9009\u62e9\u6709\u6548\u8d26\u6237', 'Please choose a valid account')
      )
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
        pickFactorPipelineMessage(
          isZh,
          `\u7eb8\u9762\u90e8\u7f72\u6210\u529f\uff1aProgram #${payload.program.id}\uff0cBinding #${payload.binding.id}`,
          `Paper deployment succeeded: Program #${payload.program.id}, Binding #${payload.binding.id}`
        )
      )
      await Promise.all([loadResearchStatus(), loadPortfolioSnapshot(), loadLiveGateSnapshot(), loadDeployments()])
    } catch (error: any) {
      setPortfolioActionError(
        error?.message
          || pickFactorPipelineMessage(isZh, '\u7eb8\u9762\u90e8\u7f72\u5931\u8d25', 'Paper deployment failed')
      )
    } finally {
      setPortfolioActionLoading(null)
    }
  }, [deployAccountId, isZh, loadDeployments, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus, setPortfolioActionError, setPortfolioActionLoading, setPortfolioActionSuccess, topPortfolioId])

  const handleDeployPortfolioLive = useCallback(async () => {
    if (!topPortfolioId) return
    if (!deployAccountId || deployAccountId <= 0) {
      setPortfolioActionError(
        pickFactorPipelineMessage(isZh, '\u8bf7\u9009\u62e9\u6709\u6548\u8d26\u6237', 'Please choose a valid account')
      )
      return
    }
    const confirmed = window.confirm(
      pickFactorPipelineMessage(
        isZh,
        '\u786e\u8ba4\u6267\u884c\u5b9e\u76d8\u90e8\u7f72\uff1f\u8fd9\u4f1a\u521b\u5efa\u53ef\u6267\u884c\u5b9e\u76d8\u7ed1\u5b9a\u3002',
        'Confirm live deployment? This will create an executable live binding.'
      )
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
        pickFactorPipelineMessage(
          isZh,
          `\u5b9e\u76d8\u90e8\u7f72\u6210\u529f\uff1aProgram #${payload.program.id}\uff0cBinding #${payload.binding.id}`,
          `Live deployment succeeded: Program #${payload.program.id}, Binding #${payload.binding.id}`
        )
      )
      await Promise.all([loadResearchStatus(), loadPortfolioSnapshot(), loadLiveGateSnapshot(), loadDeployments()])
    } catch (error: any) {
      setPortfolioActionError(
        error?.message
          || pickFactorPipelineMessage(isZh, '\u5b9e\u76d8\u90e8\u7f72\u5931\u8d25', 'Live deployment failed')
      )
    } finally {
      setPortfolioActionLoading(null)
    }
  }, [deployAccountId, isZh, loadDeployments, loadLiveGateSnapshot, loadPortfolioSnapshot, loadResearchStatus, setPortfolioActionError, setPortfolioActionLoading, setPortfolioActionSuccess, topPortfolioId])

  return {
    handleDeployPortfolioLive,
    handleDeployPortfolioPaper,
    handleResearchRun,
  }
}
