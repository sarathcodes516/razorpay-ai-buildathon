// WireTrace.tsx
import { useEffect, useRef, useState } from 'react'
import type { WireEvent } from './types'

function statusColor(status?: number) {
  if (status === undefined) return 'text-ink-500'
  if (status < 300) return 'text-ink-200'
  if (status < 500) return 'text-ink-300'
  return 'text-red-400'
}

function WireRow({ event }: { event: WireEvent }) {
  const [open, setOpen] = useState(false)
  const inFlight = event.direction === 'request'

  return (
    <div className="border-b border-ink-700">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-ink-800 transition-colors"
      >
        <span className="text-[10px] font-mono text-ink-500 w-16 shrink-0 tabular-nums">
          {new Date(event.timestamp).toLocaleTimeString('en-IN', { hour12: false })}
        </span>
        <span className="text-xs font-mono text-ink-300 w-10 shrink-0">{event.method}</span>
        <span className="text-xs font-mono text-ink-100 truncate flex-1">{event.path}</span>
        {event.signed && (
          <span className="text-[9px] font-mono border border-ink-700 text-ink-400 px-1.5 py-0.5 rounded shrink-0">
            signed
          </span>
        )}
        <span className={`text-xs font-mono w-12 text-right shrink-0 tabular-nums ${
          inFlight ? 'text-[#444] animate-pulse' : statusColor(event.status)
        }`}>
          {inFlight ? '···' : event.status}
        </span>
        {event.latencyMs !== undefined && (
          <span className="text-[10px] font-mono text-ink-500 w-14 text-right shrink-0 tabular-nums">
            {event.latencyMs}ms
          </span>
        )}
      </button>
      {open && (
        <div className="px-4 pb-3 bg-ink-800 border-t border-ink-700">
          {event.note && <p className="text-xs font-mono text-red-400 mb-2 pt-2">{event.note}</p>}
          <pre className="text-[11px] font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap text-ink-300 pt-2">
            {JSON.stringify({ headers: event.headers, body: event.body }, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export function WireTrace({ events, settlement, catalog }: { events: WireEvent[]; settlement?: { execution: any; bounds_action?: string; mandate_ceiling?: number } | null; catalog?: { ok: boolean; item_count: number; signature: string } | null }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events, settlement, catalog])

  return (
    <div className="h-full flex flex-col bg-ink-900 overflow-hidden">
      <div className="flex-none px-4 py-3.5 border-b border-ink-700">
        <p className="text-xs font-medium text-ink-300 uppercase tracking-wide">HTTP Wire Log</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {catalog && (
          <div className={`px-4 py-3 border-b border-ink-700 ${
            catalog.ok ? 'bg-[#101725]' : 'bg-[#1f1010]'
          }`}>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-[10px] font-mono text-ink-500 w-16 shrink-0 tabular-nums">
                {new Date().toLocaleTimeString('en-IN', { hour12: false })}
              </span>
              <span className="text-xs font-mono text-green-400 w-10 shrink-0">GET</span>
              <span className="text-xs font-mono text-ink-100 truncate flex-1">/api/catalog/agent</span>
              <span className={`text-[9px] font-mono border px-1.5 py-0.5 rounded shrink-0 ${
                catalog.ok
                  ? 'border-indigo-500/30 text-indigo-300'
                  : 'border-red-500/30 text-red-400'
              }`}>signed</span>
              <span className="text-xs font-mono text-green-400 w-12 text-right shrink-0 tabular-nums">200</span>
            </div>
            <div className="mt-1 ml-[88px] text-[10px] font-mono leading-relaxed">
              <p className={catalog.ok ? 'text-green-400' : 'text-red-400'}>
                [{catalog.ok ? 'sig verified' : 'sig INVALID'}] {catalog.ok ? 'payload integrity intact' : 'rejecting catalog'} · {catalog.item_count} items
              </p>
              {catalog.signature && (
                <p className="text-indigo-300/70 truncate">
                  Ed25519 sig: {catalog.signature.slice(0, 48)}…
                </p>
              )}
            </div>
          </div>
        )}
        {settlement && (
          <div className="px-4 py-3 border-b border-ink-700 bg-[#0e1a10] space-y-1.5">
            <p className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider">[SETTLEMENT] Autonomous execution</p>
            <p className="text-xs font-mono text-emerald-300">
              [SETTLEMENT] Bounds engine: {settlement.bounds_action || 'EXECUTE'} Rule: ₹{settlement.execution?.amount} {'<='} ₹{settlement.mandate_ceiling} → PASS
            </p>
            <p className="text-xs font-mono text-blue-300">
              [RAZORPAY] Test Order Created: {settlement.execution?.razorpay_order_id} (Receipt: {settlement.execution?.receipt})
            </p>
            <p className="text-[10px] font-mono text-gray-500 truncate">
              [CRYPTO] Signed by Merchant (Ed25519): {settlement.execution?.settlement_signature?.slice(0, 32)}…
            </p>
          </div>
        )}
        {events.length === 0 && !settlement && !catalog ? (
          <p className="px-4 py-4 text-sm text-ink-500">
            Run the agent to see wire events...
          </p>
        ) : (
          events.map(e => <WireRow key={e.id} event={e} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
