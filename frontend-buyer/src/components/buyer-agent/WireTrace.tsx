// WireTrace.tsx
import { useEffect, useRef, useState } from 'react'
import type { WireEvent } from './types'

function statusColor(status?: number) {
  if (status === undefined) return 'text-[#555]'
  if (status < 300) return 'text-[#aaa]'
  if (status < 500) return 'text-[#777]'
  return 'text-red-400'
}

function WireRow({ event }: { event: WireEvent }) {
  const [open, setOpen] = useState(false)
  const inFlight = event.direction === 'request'

  return (
    <div className="border-b border-[#1e1e1e]">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-[#161616] transition-colors"
      >
        <span className="text-[10px] font-mono text-[#555] w-16 shrink-0 tabular-nums">
          {new Date(event.timestamp).toLocaleTimeString('en-IN', { hour12: false })}
        </span>
        <span className="text-xs font-mono text-[#888] w-10 shrink-0">{event.method}</span>
        <span className="text-xs font-mono text-[#ccc] truncate flex-1">{event.path}</span>
        {event.signed && (
          <span className="text-[9px] font-mono border border-[#333] text-[#666] px-1.5 py-0.5 rounded shrink-0">
            signed
          </span>
        )}
        <span className={`text-xs font-mono w-12 text-right shrink-0 tabular-nums ${
          inFlight ? 'text-[#444] animate-pulse' : statusColor(event.status)
        }`}>
          {inFlight ? '···' : event.status}
        </span>
        {event.latencyMs !== undefined && (
          <span className="text-[10px] font-mono text-[#555] w-14 text-right shrink-0 tabular-nums">
            {event.latencyMs}ms
          </span>
        )}
      </button>
      {open && (
        <div className="px-4 pb-3 bg-[#111] border-t border-[#1e1e1e]">
          {event.note && <p className="text-xs font-mono text-red-400 mb-2 pt-2">{event.note}</p>}
          <pre className="text-[11px] font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap text-[#777] pt-2">
            {JSON.stringify({ headers: event.headers, body: event.body }, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export function WireTrace({ events }: { events: WireEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  return (
    <div className="h-full flex flex-col bg-[#0d0d0d] overflow-hidden">
      <div className="flex-none px-4 py-3.5 border-b border-[#222]">
        <p className="text-xs font-medium text-[#888] uppercase tracking-wide">HTTP Wire Log</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <p className="px-4 py-4 text-sm text-[#555]">
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
