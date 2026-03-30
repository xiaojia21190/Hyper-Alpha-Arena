import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { BarChart3, Play, RefreshCw } from 'lucide-react'
import FactorDeploymentsStage from './pipeline/FactorDeploymentsStage'
import FactorLiveGateStage from './pipeline/FactorLiveGateStage'
import FactorResearchStage from './pipeline/FactorResearchStage'
import {
  getViewDescription,
  getViewTitle,
  type FactorPipelineView,
} from './pipeline/shared'
import { useFactorPipelineData } from './pipeline/useFactorPipelineData'

export type { FactorPipelineView }

export default function FactorPipelineWorkspace({ view }: { view: FactorPipelineView }) {
  const { i18n } = useTranslation()
  const isZh = Boolean(i18n.language?.startsWith('zh'))
  const {
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
  } = useFactorPipelineData(view, isZh)

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
              {isZh ? '\u5237\u65b0' : 'Refresh'}
            </Button>
            {view === 'research' && (
              <Button size="sm" onClick={handleResearchRun} disabled={researchStarting || researchIsRunning}>
                {researchStarting || researchIsRunning
                  ? <RefreshCw className="mr-1 h-3.5 w-3.5 animate-spin" />
                  : <Play className="mr-1 h-3.5 w-3.5" />}
                {researchIsRunning
                  ? (isZh ? '\u7814\u7a76\u8fd0\u884c\u4e2d' : 'Research running')
                  : (isZh ? '\u8fd0\u884c\u4e00\u6b21' : 'Run once')}
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
