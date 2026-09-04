// BuyerAgentApp.tsx
import { useState } from 'react'
import { ChatPanel } from './ChatPanel'
import { WireTrace } from './WireTrace'
import { useAgentSession } from './useAgentSession'

export function BuyerAgentApp({ mandateId }: { mandateId: string }) {
  const { state, start } = useAgentSession()
  const [mobileTab, setMobileTab] = useState<'chat' | 'wire'>('chat')

  return (
    <div className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0 bg-ink-900">

      {/* Mobile tab switcher */}
      <div className="md:hidden flex border-b border-ink-700 flex-none">
        {(['chat', 'wire'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setMobileTab(tab)}
            className={[
              'flex-1 py-2.5 text-xs font-medium border-b-2 transition-colors',
              mobileTab === tab
                ? 'border-white text-white'
                : 'border-transparent text-ink-400',
            ].join(' ')}
          >
            {tab === 'chat' ? 'Chat' : 'Wire'}
          </button>
        ))}
      </div>

      {/* Chat */}
      <div className={`${mobileTab === 'chat' ? 'flex' : 'hidden'} md:flex md:w-[52%] border-r border-ink-700 overflow-hidden`}>
        <ChatPanel state={state} onStart={start} defaultMandateId={mandateId} />
      </div>

      {/* Wire trace */}
      <div className={`${mobileTab === 'wire' ? 'flex' : 'hidden'} md:flex md:w-[48%] overflow-hidden`}>
        <WireTrace events={state.wire} settlement={state.settlement} catalog={state.catalog} />
      </div>
    </div>
  )
}
