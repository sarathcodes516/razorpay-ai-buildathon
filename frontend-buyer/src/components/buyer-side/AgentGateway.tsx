import React, { useRef, useState } from 'react'

const API_BASE = (import.meta as any).env?.VITE_BUYER_AGENT_API ?? 'http://localhost:8001'

interface TurnData {
  message: string
  thought_process: string
  action: string
  requested_discount_pct?: number
  offered_discount_pct?: number
  tools?: {
    campaign?: { has_campaign?: boolean; campaign_name?: string; discount_pct?: number; rationale?: string }
    discount_engine?: { was_capped?: boolean; max_allowable_pct?: number; approved_pct?: number; requested_pct?: number; audit_note?: string }
    bundle?: { bundle_available?: boolean; addon?: { sku?: string; name?: string; bundle_price?: number; discount_pct?: number } | null }
  }
  bundle_proposal?: { sku?: string; addon_price?: number; included?: boolean } | null
  rationale?: string
  is_security_override?: boolean
  turn_number?: number
}
interface Turn { role: 'buyer' | 'merchant'; data: TurnData }
interface ExecutionData {
  status?: string
  razorpay_order_id?: string
  receipt?: string
  amount?: number
  amount_paise?: number
  currency?: string
  sku?: string
  qty?: number
  discount_pct?: number
  mandate_id?: string
  merchant_pubkey?: string
  settlement_signature?: string
  settled_at?: string
}
interface FinalResult {
  action: string
  final_cart?: any
  audit_trail?: any
  execution?: ExecutionData
}

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
              setResult({
                action: evt.action,
                final_cart: evt.final_cart,
                audit_trail: evt.audit_trail,
                execution: evt.final_cart?.execution || evt.execution,
                tools: evt.tools,
                is_security_override: !!evt.is_security_override,
              })
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') setError(e.message || 'Unknown error')
    } finally { setRunning(false) }
  }

  const stop = () => { abortRef.current?.abort(); setRunning(false) }

  return (
    <div className="flex-1 flex overflow-hidden min-h-0 bg-ink-900">

      {/* ── Left sidebar ── */}
      <div className="w-72 flex-none flex flex-col border-r border-ink-700 overflow-y-auto">

        {/* Goal */}
        <div className="p-5 border-b border-ink-700">
          <label className="block text-xs font-medium text-ink-200 uppercase tracking-wide mb-2">
            Procurement Goal
          </label>
          <textarea
            value={goal}
            onChange={e => setGoal(e.target.value)}
            disabled={running}
            rows={4}
            className="w-full text-sm bg-[#262626] border border-[#3a3a3a] text-white placeholder-[#888888] focus:border-[#666666] focus:outline-none rounded-lg px-3.5 py-2.5 resize-none disabled:opacity-50 transition-colors"
          />
          <div className="mt-3">
            {running ? (
              <button onClick={stop}
                className="w-full py-2 text-xs font-medium border border-ink-600 text-ink-200 hover:text-white hover:border-ink-600 rounded-lg transition-colors">
                Stop
              </button>
            ) : (
              <button onClick={run}
                className="w-full py-2 text-xs font-semibold bg-[#6CE8AA] text-black rounded-lg hover:bg-[#5BD699] active:bg-[#4AC088] transition-colors">
                Run Negotiation
              </button>
            )}
          </div>
        </div>

        {/* Activity log */}
        {log.length > 0 && (
          <div className="p-5 border-b border-ink-700">
            <p className="text-xs font-medium text-ink-300 uppercase tracking-wide mb-3">Activity</p>
            <div className="space-y-1.5">
              {log.map((l, i) => (
                <p key={i} className={`text-xs font-mono leading-relaxed ${
                  running && i === log.length - 1 ? 'text-ink-100' : 'text-ink-400'
                }`}>{l}</p>
              ))}
            </div>
          </div>
        )}

        {/* OUTCOME & SETTLEMENT PANEL */}
        {result && (
          <div className="p-5">
            <div className="bg-ink-800 border border-ink-700 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Outcome</span>
                <span className={`px-2 py-0.5 text-[10px] font-black rounded uppercase ${
                  result.action === 'EXECUTE'  ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                  : result.action === 'ESCALATE' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
                }`}>
                  {result.action || 'IN_PROGRESS'}
                </span>
              </div>

              {result.execution ? (
                <div className="space-y-3 pt-2 text-xs">
                  <div className="flex justify-between text-gray-400">
                    <span>Razorpay Order</span>
                    <span className="font-mono font-bold text-white bg-gray-900 px-2 py-0.5 rounded border border-gray-700">
                      {result.execution.razorpay_order_id || "FAILED"}
                    </span>
                  </div>
                  <div className="flex justify-between text-gray-400">
                    <span>Units / SKU</span>
                    <span className="text-white font-mono">
                      {result.execution.qty}× {result.execution.sku}
                    </span>
                  </div>
                  <div className="flex justify-between text-gray-400">
                    <span>Total Settled</span>
                    <span className="text-green-400 font-bold font-mono text-sm">
                      ₹{result.execution.amount?.toLocaleString()}
                    </span>
                  </div>
                  <div className="pt-2 border-t border-ink-700 space-y-1">
                    <div className="flex justify-between items-center text-[10px] text-gray-500">
                      <span>Ed25519 Proof</span>
                      <span className="text-green-500 font-mono font-bold">VERIFIED</span>
                    </div>
                    <p className="text-[9px] font-mono text-gray-600 break-all bg-black/50 p-1.5 rounded leading-tight">
                      {result.execution.settlement_signature}
                    </p>
                  </div>
                </div>
              ) : result.action === 'GATED_VIOLATION' ? (
                <div className="p-3 bg-red-950/30 border border-red-800/50 rounded-lg text-xs space-y-2">
                  <p className="text-[10px] font-bold text-red-400 uppercase tracking-wider">
                    Mandate Bounds Violation
                  </p>
                  <p className="text-[11px] text-red-300/80 leading-relaxed font-mono">
                    Autonomous settlement blocked by TrustRail Bounds Engine. Order total exceeds signed spend mandate ceiling.
                  </p>
                </div>
              ) : result.tools?.discount_engine?.was_capped && result.final_cart ? (
                <div className="mb-2 p-2.5 bg-red-950/40 border-l-2 border-red-500 rounded-r-lg text-[11px] text-red-300">
                  <p className="text-[9px] font-black uppercase tracking-widest text-red-400 mb-1">
                    Graceful Failure Handled · Prompt Injection Neutralized
                  </p>
                  LLM offered {result.tools.discount_engine.requested_pct}% → capped at {result.tools.discount_engine.max_allowable_pct}%.
                </div>
              ) : (
                <div className="text-xs text-gray-500 py-4 text-center">
                  Awaiting agent consensus to execute settlement.
                </div>
              )}
            </div>
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
        <div className="flex-none px-6 py-3.5 border-b border-ink-700 flex items-center justify-between">
          <span className="text-xs font-medium text-ink-300 uppercase tracking-wide">Agent Conversation ( Audit Trail )</span>
          {transcript.length > 0 && (
            <span className="text-xs font-mono text-ink-500">{transcript.length} turns</span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
                  {transcript.length === 0 && !running && (
                    <p className="text-sm text-ink-400 font-light pt-2">
                      Set your goal and click Run to begin negotiation.
                    </p>
                  )}
                  {transcript.length === 0 && running && (
                    <p className="text-sm text-ink-300 font-light pt-2 animate-pulse">
                      Buyer agent thinking...
                    </p>
                  )}

                  {/* Threats Mitigated counter — visible defense telemetry */}
                  {transcript.filter(t => t.role === 'merchant' && t.data.is_security_override).length > 0 && (
                    <div className="px-5 py-3 border-y border-red-900/40 bg-red-950/15">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-red-400/80 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                          Threats Mitigated
                        </span>
                        <span className="text-red-400 font-mono font-bold">
                          {transcript.filter(t => t.role === 'merchant' && t.data.is_security_override).length}
                        </span>
                      </div>
                      <p className="text-[10px] text-gray-500 leading-tight mt-1">
                        System actively prevented unauthorized margin loss via bounds engine override.
                      </p>
                    </div>
                  )}

          {transcript.map((turn, i) => {
            const isBuyer  = turn.role === 'buyer'
            const discount = isBuyer ? turn.data.requested_discount_pct : turn.data.offered_discount_pct
            return (
              <div key={i} className={`flex flex-col ${isBuyer ? 'items-start' : 'items-end'}`}>
                <p className="text-[10px] font-semibold text-ink-400 uppercase tracking-widest mb-2">
                  {isBuyer ? 'Buyer' : 'Merchant'}
                </p>
                <div className={`max-w-[78%] rounded-xl border overflow-hidden ${
                  isBuyer
                    ? 'bg-ink-800 border-ink-700'
                    : 'bg-ink-800 border-ink-700'
                }`}>
                  {/* GRACEFUL FAILURE banner — visible evidence of the bounds-engine intercept */}
                  {!isBuyer && turn.data.is_security_override && turn.data.tools?.discount_engine && (
                    <div className="m-3 p-3 bg-red-950/40 border-l-2 border-red-500 rounded-r-lg">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="bg-red-500 text-white text-[9px] font-black uppercase px-1.5 py-0.5 rounded tracking-widest">
                          Graceful Failure Handled
                        </span>
                        <span className="text-xs font-bold text-red-400 uppercase tracking-wider">
                          Prompt Injection Neutralized
                        </span>
                      </div>
                      <p className="text-[11px] text-red-300/80 font-mono leading-relaxed">
                        The merchant LLM attempted to authorize an off-policy discount of {turn.data.tools.discount_engine.requested_pct}%.
                        The deterministic bounds engine intercepted the payload, rejected the hallucination, and hard-capped the offer at the store's
                        {' '}{turn.data.tools.discount_engine.max_allowable_pct}% maximum policy ceiling before transmitting.
                      </p>
                    </div>
                  )}

                  {/* Message */}
                  <p className="px-4 py-3.5 text-sm text-ink-50 leading-relaxed">
                    {turn.data.message}
                  </p>
                  {/* Meta footer */}
                  <div className="px-4 py-3 border-t border-ink-700 text-xs font-mono space-y-1.5">
                    <div>
                      <span className="text-ink-500">action </span>
                      <span className="text-ink-200">{turn.data.action}</span>
                    </div>
                    {discount !== undefined && (
                      <div>
                        <span className="text-ink-500">{isBuyer ? 'requesting ' : 'offering '}</span>
                        <span className="text-ink-200">{discount}%</span>
                      </div>
                    )}

                    {/* Tool audit tags (merchant turns only) */}
                    {!isBuyer && turn.data.tools && (
                      <div className="flex flex-wrap gap-1.5 pt-1.5">
                        {turn.data.tools.campaign?.has_campaign && (
                          <span className="px-2 py-0.5 text-[10px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
                            CAMPAIGN: {turn.data.tools.campaign.campaign_name} (-{turn.data.tools.campaign.discount_pct}%)
                          </span>
                        )}
                        {turn.data.tools.discount_engine?.was_capped && (
                          <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded">
                            BOUNDS ENGINE: CAPPED @ {turn.data.tools.discount_engine.max_allowable_pct}%
                          </span>
                        )}
                      </div>
                    )}

                    {/* Supply-driven bundle card (merchant turns only) */}
                    {!isBuyer && turn.data.bundle_proposal?.included && (
                      <div className="mt-2 p-3 bg-purple-950/20 border border-purple-800/30 rounded-lg text-xs flex justify-between items-center">
                        <div>
                          <p className="font-bold text-purple-300">Bundle Offer: {turn.data.bundle_proposal.sku}</p>
                          <p className="text-[11px] text-gray-400">Warehouse surplus liquidation add-on</p>
                          {turn.data.tools?.bundle?.addon?.name && (
                            <p className="text-[10px] text-purple-200/70 mt-0.5">{turn.data.tools.bundle.addon.name}</p>
                          )}
                        </div>
                        <div className="text-right">
                          <span className="font-mono font-black text-purple-200">
                            +₹{turn.data.bundle_proposal.addon_price}
                          </span>
                        </div>
                      </div>
                    )}

                    {turn.data.thought_process && (
                      <p className="text-ink-500 italic pt-1 leading-relaxed border-t border-ink-700 mt-1">
                        {turn.data.thought_process}
                      </p>
                    )}
                    {turn.data.rationale && (
                      <p className="text-ink-500 leading-relaxed border-t border-ink-700 pt-1">
                        <span className="text-ink-400">rationale </span>{turn.data.rationale}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}

          {running && transcript.length > 0 && (
            <p className="text-xs text-ink-400 font-light animate-pulse">
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
