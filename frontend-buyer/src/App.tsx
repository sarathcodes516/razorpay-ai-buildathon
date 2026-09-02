import { useState } from 'react'
import { BuyerAgentApp } from './components/buyer-agent/BuyerAgentApp'
import MandateConfigurator from './components/buyer-side/MandateConfigurator'
import AgentGateway from './components/buyer-side/AgentGateway'

const tabs = [
  { id: 'mandate', label: 'Issue Mandate' },
  { id: 'gateway', label: 'Negotiate'     },
  { id: 'direct',  label: 'Wire Protocol' },
] as const

type Tab = typeof tabs[number]['id']

export default function App() {
  const [active,    setActive]    = useState<Tab>('mandate')
  const [mandateId, setMandateId] = useState('')

  const handleMandateCreated = (id: string) => {
    setMandateId(id)
    setActive('gateway')
  }

  return (
    <div className="flex flex-col h-screen bg-[#0d0d0d] text-white overflow-hidden">

      {/* Top bar */}
      <header className="flex-none border-b border-[#2a2a2a]">
        <div className="px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold tracking-tight text-white">TrustRail</span>
            <span className="text-xs text-[#666] font-light">Procurement Agent</span>
          </div>
          {mandateId && (
            <span className="text-xs font-mono text-[#888]">
              mandate&nbsp;<span className="text-[#ccc]">{mandateId}</span>
            </span>
          )}
        </div>

        {/* Tabs */}
        <div className="px-6 flex gap-1">
          {tabs.map(tab => {
            const locked   = tab.id !== 'mandate' && !mandateId
            const isActive = active === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => !locked && setActive(tab.id)}
                disabled={locked}
                className={[
                  'px-4 py-2.5 text-xs font-medium border-b-2 transition-colors duration-150',
                  isActive ? 'border-white text-white'
                  : locked ? 'border-transparent text-[#3a3a3a] cursor-not-allowed'
                           : 'border-transparent text-[#888] hover:text-[#ccc]',
                ].join(' ')}
              >
                {tab.label}
              </button>
            )
          })}
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-hidden flex flex-col min-h-0">
        {active === 'mandate' && (
          <div className="flex-1 overflow-y-auto">
            <MandateConfigurator onMandateCreated={handleMandateCreated} />
          </div>
        )}
        {active === 'gateway' && mandateId && (
          <AgentGateway mandateId={mandateId} />
        )}
        {active === 'direct' && mandateId && (
          <BuyerAgentApp mandateId={mandateId} />
        )}
      </main>
    </div>
  )
}
