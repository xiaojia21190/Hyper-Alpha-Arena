import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Play, RefreshCw, Rocket } from 'lucide-react'
import type { FactorPortfolioCandidate, FactorPortfolioDeploymentRecord } from '@/lib/api'
import { formatIso, formatNumber } from './shared'

interface FactorDeploymentsStageProps {
  isZh: boolean
  topPortfolio: FactorPortfolioCandidate | null
  topPortfolioId: number
  portfolioLoading: boolean
  availableAccounts: Array<{ id: number; name: string }>
  deployAccountId: number
  onDeployAccountChange: (value: number) => void
  portfolioActionLoading: 'paper' | 'live' | null
  portfolioActionError: string
  portfolioActionSuccess: string
  portfolioLeaderboard: FactorPortfolioCandidate[]
  deployments: FactorPortfolioDeploymentRecord[]
  deploymentsLoading: boolean
  onDeployPortfolioPaper: () => void
  onDeployPortfolioLive: () => void
}

export default function FactorDeploymentsStage({
  isZh,
  topPortfolio,
  topPortfolioId,
  portfolioLoading,
  availableAccounts,
  deployAccountId,
  onDeployAccountChange,
  portfolioActionLoading,
  portfolioActionError,
  portfolioActionSuccess,
  portfolioLeaderboard,
  deployments,
  deploymentsLoading,
  onDeployPortfolioPaper,
  onDeployPortfolioLive,
}: FactorDeploymentsStageProps) {
  return (
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
              <div className="mt-1 break-all text-sm font-semibold">{topPortfolio.name}</div>
              <div className="mt-1 font-mono text-xs text-muted-foreground">{topPortfolio.construction_method}</div>
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
                <Select
                  value={String(deployAccountId || availableAccounts[0].id)}
                  onValueChange={(value) => onDeployAccountChange(Number(value))}
                >
                  <SelectTrigger className="h-8">
                    <SelectValue />
                  </SelectTrigger>
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
                  onChange={(e) => onDeployAccountChange(Number(e.target.value || 0))}
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
          <Button size="sm" disabled={!topPortfolioId || portfolioActionLoading !== null} onClick={onDeployPortfolioPaper}>
            {portfolioActionLoading === 'paper'
              ? <RefreshCw className="h-3.5 w-3.5 mr-1 animate-spin" />
              : <Play className="h-3.5 w-3.5 mr-1" />}
            {isZh ? '部署到纸面' : 'Deploy to paper'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!topPortfolioId || portfolioActionLoading !== null}
            onClick={onDeployPortfolioLive}
          >
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
              <div
                key={`${row.name}-${index}`}
                className="flex flex-wrap items-center gap-3 rounded-lg border bg-background/70 px-3 py-2 text-sm"
              >
                <Badge variant="outline" className="font-mono">
                  #{index + 1}
                </Badge>
                <span className="min-w-[130px] font-medium">{row.name}</span>
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

      <div className="min-h-0 rounded-lg border bg-background/80 p-4 space-y-3">
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
  )
}
