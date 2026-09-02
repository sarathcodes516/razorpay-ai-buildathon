import React, { useRef, useState } from 'react'

const API_BASE = (import.meta as any).env?.VITE_BUYER_AGENT_API ?? 'http://localhost:8001'

interface TurnData {
  message: string
  thought_process: string
  action: string
  requested_discount_pct?: number
  offered_discount_pct?: number
}
interface Turn { role: 'buyer' | 'merchant'; data: TurnData }
interface FinalResult { action: string; final_cart?: any; audit_trail?: any }

export default function AgentGateway({ mandateId }: { mandateId: string }) {
  const [goal,       setGoal]       = useState('I need 15 Graphic Tees for a crew event. My budget is ₹50,000.')
  const [running,    setRunning]    = useState(false)
  const [log,        setLog]        = useState<string[]>([])
  const [transcript, setTranscript] = useState<Turn[]>([])
  const [result,     setResult]     = useState<FinalResult | null>(null)
  const [error,      setError]      = useState<string | null>(null)
  const abortRef  = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const run = async () => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setRunning(true); setLog([]); setTranscript([]); setResult(null); setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/gateway/negotiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mandate_id: mandateId, procurement_goal: goal }),
        signal: ctrl.signal,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      const reader = res.body!.getReader()
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const evt = JSON.parse(line)
            if (evt.type === 'log')  setLog(p => [...p, evt.message])
            if (evt.type === 'turn') {
              setTranscript(p => [...p, { role: evt.role, data: evt.data }])
              setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
            }
            if (evt.type === 'status' && evt.status === 'done')
              setResult({ action: evt.action, final_cart: evt.final_cart, audit_trail: evt.audit_trail })
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') setError(e.message || 'Unknown error')
    } finally { setRunning(false) }
  }

  const stop = () => { abortRef.current?.abort(); setRunning(false) }

  return (
    <div className="flex-1 flex overflow-hidden min-h-0 bg-[#0d0d0d]">

      {/* ── Left sidebar ── */}
      <div className="w-72 flex-none flex flex-col border-r border-[#222] overflow-y-auto">

        {/* Goal */}
        <div className="p-5 border-b border-[#222]">
          <label className="block text-xs font-medium text-[#aaa] uppercase tracking-wide mb-2">
            Procurement Goal
          </label>
          <textarea
            value={goal}
            onChange={e => setGoal(e.target.value)}
            disabled={running}
            rows={4}
            className="w-full text-sm bg-[#1a1a1a] border border-[#333] text-white placeholder-[#555] focus:border-[#666] focus:outline-none rounded-lg px-3.5 py-2.5 resize-none disabled:opacity-50 transition-colors"
          />
          <div className="mt-3">
            {running ? (
              <button onClick={stop}
                className="w-full py-2 text-xs font-medium border border-[#444] text-[#aaa] hover:text-white hover:border-[#666] rounded-lg transition-colors">
                Stop
              </button>
            ) : (
              <button onClick={run}
                className="w-full py-2 text-xs font-semibold bg-white text-black rounded-lg hover:bg-[#e5e5e5] transition-colors">
                Run Negotiation
              </button>
            )}
          </div>
        </div>

        {/* Activity log */}
        {log.length > 0 && (
          <div className="p-5 border-b border-[#222]">
            <p className="text-xs font-medium text-[#888] uppercase tracking-wide mb-3">Activity</p>
            <div className="space-y-1.5">
              {log.map((l, i) => (
                <p key={i} className={`text-xs font-mono leading-relaxed ${
                  running && i === log.length - 1 ? 'text-[#ccc]' : 'text-[#666]'
                }`}>{l}</p>
              ))}
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="p-5">
            <p className="text-xs font-medium text-[#888] uppercase tracking-wide mb-3">Outcome</p>
            <p className={`text-sm font-semibold mb-4 ${
              result.action === 'EXECUTE'  ? 'text-white'   :
              result.action === 'ESCALATE' ? 'text-[#aaa]'  : 'text-[#666]'
            }`}>{result.action}</p>
            {result.final_cart && (
              <div className="space-y-2.5 text-sm border-t border-[#2a2a2a] pt-3">
                {([
                  ['Units',    result.final_cart.items?.reduce((s: number, i: any) => s + i.qty, 0)],
                  ['Subtotal', `₹${result.final_cart.subtotal?.toLocaleString()}`],
                  ['Discount', `${result.final_cart.discount_pct}%`],
                  ['Total',    `₹${result.final_cart.final_amount?.toLocaleString()}`],
                ] as [string, any][]).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-[#888]">{k}</span>
                    <span className="text-white font-medium">{v}</span>
                  </div>
                ))}
                {result.audit_trail && (
                  <p className={`mt-1 pt-3 border-t border-[#2a2a2a] text-xs ${
                    result.audit_trail.evaluated?.includes('PASS') ? 'text-[#aaa]' : 'text-[#666]'
                  }`}>{result.audit_trail.evaluated}</p>
                )}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="p-5">
            <p className="text-sm text-red-400 bg-red-950/60 border border-red-800 rounded-lg px-4 py-3">
              {error}
            </p>
          </div>
        )}
      </div>

      {/* ── Transcript ── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <div className="flex-none px-6 py-3.5 border-b border-[#222] flex items-center justify-between">
          <span className="text-xs font-medium text-[#888] uppercase tracking-wide">Agent Conversation</span>
          {transcript.length > 0 && (
            <span className="text-xs font-mono text-[#555]">{transcript.length} turns</span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {transcript.length === 0 && !running && (
            <p className="text-sm text-[#666] font-light pt-2">
              Set your goal and click Run to begin negotiation.
            </p>
          )}
          {transcript.length === 0 && running && (
            <p className="text-sm text-[#888] font-light pt-2 animate-pulse">
              Buyer agent thinking...
            </p>
          )}

          {transcript.map((turn, i) => {
            const isBuyer  = turn.role === 'buyer'
            const discount = isBuyer ? turn.data.requested_discount_pct : turn.data.offered_discount_pct
            return (
              <div key={i} className={`flex flex-col ${isBuyer ? 'items-start' : 'items-end'}`}>
                <p className="text-[10px] font-semibold text-[#666] uppercase tracking-widest mb-2">
                  {isBuyer ? 'Buyer' : 'Merchant'}
                </p>
                <div className={`max-w-[78%] rounded-xl border overflow-hidden ${
                  isBuyer
                    ? 'bg-[#161616] border-[#2e2e2e]'
                    : 'bg-[#131313] border-[#262626]'
                }`}>
                  {/* Message */}
                  <p className="px-4 py-3.5 text-sm text-[#e5e5e5] leading-relaxed">
                    {turn.data.message}
                  </p>
                  {/* Meta footer */}
                  <div className="px-4 py-3 border-t border-[#222] text-xs font-mono space-y-1.5">
                    <div>
                      <span className="text-[#555]">action </span>
                      <span className="text-[#aaa]">{turn.data.action}</span>
                    </div>
                    {discount !== undefined && (
                      <div>
                        <span className="text-[#555]">{isBuyer ? 'requesting ' : 'offering '}</span>
                        <span className="text-[#aaa]">{discount}%</span>
                      </div>
                    )}
                    {turn.data.thought_process && (
                      <p className="text-[#555] italic pt-1 leading-relaxed border-t border-[#1e1e1e] mt-1">
                        {turn.data.thought_process}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}

          {running && transcript.length > 0 && (
            <p className="text-xs text-[#666] font-light animate-pulse">
              {transcript[transcript.length - 1].role === 'buyer'
                ? 'Merchant evaluating...'
                : 'Buyer thinking...'}
            </p>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
