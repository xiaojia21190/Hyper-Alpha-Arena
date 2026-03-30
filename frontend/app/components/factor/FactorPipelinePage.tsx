import { useCallback, useEffect, useMemo, useState } from 'react'
import { FlaskConical, Rocket, ShieldAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import FactorPipelineWorkspace, { type FactorPipelineView } from './FactorPipelineWorkspace'

export const FACTOR_PIPELINE_PAGE = 'factor-pipeline' as const

export type FactorPipelineStage = FactorPipelineView

const DEFAULT_FACTOR_PIPELINE_STAGE: FactorPipelineStage = 'research'
const FACTOR_PIPELINE_STAGES = new Set<string>(['research', 'deployments', 'live-gate'])

const LEGACY_FACTOR_PIPELINE_PAGE_STAGES: Record<string, FactorPipelineStage> = {
  'factor-research-workspace': 'research',
  'factor-portfolio-deployments': 'deployments',
  'factor-live-gate': 'live-gate',
  'factor-library': 'research',
}

interface ResolvedFactorPipelineRoute {
  canonicalHash: string
  stage: FactorPipelineStage
}

function splitHashRoute(rawHash: string): { page: string; searchParams: URLSearchParams } {
  const queryIndex = rawHash.indexOf('?')
  if (queryIndex === -1) {
    return { page: rawHash, searchParams: new URLSearchParams() }
  }

  return {
    page: rawHash.slice(0, queryIndex),
    searchParams: new URLSearchParams(rawHash.slice(queryIndex + 1)),
  }
}

function normalizeFactorPipelineStage(stage: string | null | undefined): FactorPipelineStage {
  if (stage && FACTOR_PIPELINE_STAGES.has(stage)) {
    return stage as FactorPipelineStage
  }

  return DEFAULT_FACTOR_PIPELINE_STAGE
}

function buildFactorPipelineHash(stage: FactorPipelineStage, searchParams?: URLSearchParams): string {
  const nextSearchParams = new URLSearchParams(searchParams)
  nextSearchParams.set('stage', stage)
  return `${FACTOR_PIPELINE_PAGE}?${nextSearchParams.toString()}`
}

export function resolveFactorPipelineRoute(rawHash: string): ResolvedFactorPipelineRoute | null {
  const { page, searchParams } = splitHashRoute(rawHash)
  const legacyStage = LEGACY_FACTOR_PIPELINE_PAGE_STAGES[page]

  if (!legacyStage && page !== FACTOR_PIPELINE_PAGE) {
    return null
  }

  const stage = legacyStage || normalizeFactorPipelineStage(searchParams.get('stage'))
  return {
    stage,
    canonicalHash: buildFactorPipelineHash(stage, searchParams),
  }
}

export default function FactorPipelinePage() {
  const { t } = useTranslation()
  const [stage, setStage] = useState<FactorPipelineStage>(() => (
    resolveFactorPipelineRoute(window.location.hash.slice(1))?.stage ?? DEFAULT_FACTOR_PIPELINE_STAGE
  ))

  const stageItems = useMemo(() => ([
    {
      value: 'research' as const,
      label: t('sidebar.factorResearchCenter', '因子研究中心'),
      icon: FlaskConical,
    },
    {
      value: 'deployments' as const,
      label: t('sidebar.portfolioDeployments', '组合部署记录'),
      icon: Rocket,
    },
    {
      value: 'live-gate' as const,
      label: t('sidebar.liveGateStatus', '实盘门控状态'),
      icon: ShieldAlert,
    },
  ]), [t])

  const syncStageFromHash = useCallback((rawHash: string) => {
    if (!rawHash) {
      setStage(DEFAULT_FACTOR_PIPELINE_STAGE)
      return
    }

    const resolvedRoute = resolveFactorPipelineRoute(rawHash)
    if (!resolvedRoute) return

    setStage(resolvedRoute.stage)
    if (resolvedRoute.canonicalHash !== rawHash) {
      window.location.hash = resolvedRoute.canonicalHash
    }
  }, [])

  useEffect(() => {
    syncStageFromHash(window.location.hash.slice(1))

    const onHashChange = () => {
      syncStageFromHash(window.location.hash.slice(1))
    }

    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [syncStageFromHash])

  const handleStageChange = useCallback((nextStage: FactorPipelineStage) => {
    const { searchParams } = splitHashRoute(window.location.hash.slice(1))
    const nextHash = buildFactorPipelineHash(nextStage, searchParams)

    setStage(nextStage)
    if (window.location.hash.slice(1) !== nextHash) {
      window.location.hash = nextHash
    }
  }, [])

  return (
    <div className="flex flex-1 min-h-0 flex-col gap-4">
      <div className="rounded-xl border bg-background/70 p-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
            {t('factorPipeline.stageLabel', 'Stage')}
          </span>
          {stageItems.map((item) => {
            const Icon = item.icon
            const isActive = item.value === stage

            return (
              <Button
                key={item.value}
                size="sm"
                variant={isActive ? 'secondary' : 'ghost'}
                className={isActive ? 'text-[#B8860B]' : ''}
                onClick={() => handleStageChange(item.value)}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Button>
            )
          })}
        </div>
      </div>

      <FactorPipelineWorkspace view={stage} />
    </div>
  )
}
