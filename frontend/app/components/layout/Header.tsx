import { useTranslation } from 'react-i18next'
import { useCurrentExchangeInfo } from '@/contexts/ExchangeContext'

interface Account {
  id: number
  user_id: number
  name: string
  account_type: string
  initial_capital: number
  current_cash: number
  frozen_cash: number
}

interface HeaderProps {
  title?: string
  currentAccount?: Account | null
  showAccountSelector?: boolean
}

export default function Header({ title = 'Hyper Alpha Arena' }: HeaderProps) {
  const { t } = useTranslation()
  const currentExchangeInfo = useCurrentExchangeInfo()

  return (
    <header className="w-full border-b bg-background/50 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="w-full py-2 px-3 md:px-4 flex items-center justify-between">
        <div className="flex items-center gap-2 md:gap-3">
          <h1 className="text-base md:text-xl font-bold truncate">{title}</h1>
          {currentExchangeInfo.id === 'hyperliquid' && (
            <span className="hidden md:inline text-xs text-muted-foreground ml-2">
              {t('header.premiumDiscount', 'Subscribe to Premium for service fee 50% off.')}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
