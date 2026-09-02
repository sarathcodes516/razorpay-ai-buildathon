import React, { useState } from 'react'
import axios from 'axios'

// Design tokens
// bg-[#0d0d0d]   page background
// bg-[#1a1a1a]   input / card surface
// border-[#333]  visible border on inputs and dividers
// border-[#444]  focused / hover border
// text-white     primary — values, headings
// text-[#aaa]    secondary — labels, descriptions
// text-[#666]    tertiary — hints, slider ticks

const inputCls =
  'w-full px-3.5 py-2.5 text-sm bg-[#1a1a1a] border border-[#333] text-white ' +
  'placeholder-[#555] focus:border-[#666] focus:outline-none rounded-lg transition-colors'

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-medium text-[#aaa] mb-1.5 tracking-wide uppercase">
      {children}
    </p>
  )
}

function Hint({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-[#666] mt-1.5 leading-relaxed">{children}</p>
}

export default function MandateConfigurator({
  onMandateCreated,
}: {
  onMandateCreated: (id: string) => void
}) {
  const [principal,   setPrincipal]   = useState('Corporate Buyer Alpha')
  const [maxTx,       setMaxTx]       = useState('5000')
  const [autoApprove, setAutoApprove] = useState('2500')
  const [maxDiscount, setMaxDiscount] = useState(15)
  const [createdId,   setCreatedId]   = useState('')
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState('')

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await axios.post('http://localhost:8001/api/mandate/dynamic', {
        principal,
        max_per_transaction:               Number(maxTx)       || 0,
        max_total_spend_today:             15000,
        allowed_categories:                ['apparel', 'accessories'],
        auto_approve_below:                Number(autoApprove) || 0,
        max_discount_agent_can_accept_pct: maxDiscount,
      })
      setCreatedId(res.data.mandate_id)
      onMandateCreated(res.data.mandate_id)
    } catch {
      setError('Failed to issue mandate — is the backend running on http://localhost:8001?')
    }
    setLoading(false)
  }

  return (
    <div className="max-w-md mx-auto px-6 py-12">
      <h1 className="text-2xl font-semibold text-white mb-1.5">Issue Spend Mandate</h1>
      <p className="text-sm text-[#888] mb-10 leading-relaxed">
        Cryptographically authorize your procurement agent
      </p>

      <form onSubmit={handleCreate} className="space-y-6">

        {/* Principal */}
        <div>
          <Label>Principal / Organization</Label>
          <input
            type="text"
            value={principal}
            onChange={e => setPrincipal(e.target.value)}
            className={inputCls}
          />
        </div>

        {/* Money fields */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Max per Transaction (₹)</Label>
            <input
              type="text"
              value={maxTx}
              onChange={e => setMaxTx(e.target.value)}
              placeholder="5000"
              className={inputCls}
            />
            <Hint>Hard ceiling per purchase</Hint>
          </div>
          <div>
            <Label>Auto-Approve Below (₹)</Label>
            <input
              type="text"
              value={autoApprove}
              onChange={e => setAutoApprove(e.target.value)}
              placeholder="2500"
              className={inputCls}
            />
            <Hint>Skips human review below this</Hint>
          </div>
        </div>

        {/* Slider */}
        <div>
          <div className="flex justify-between items-baseline mb-3">
            <Label>Anomaly Discount Threshold</Label>
            <span className="text-base font-semibold text-white tabular-nums">{maxDiscount}%</span>
          </div>
          <input
            type="range"
            min={0} max={100} step={1}
            value={maxDiscount}
            onChange={e => setMaxDiscount(Number(e.target.value))}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-[#666] mt-2">
            <span>0%</span><span>50%</span><span>100%</span>
          </div>
          <Hint>Discounts above this threshold are flagged for human review</Hint>
        </div>

        {/* Summary */}
        <div className="border-t border-[#2a2a2a] pt-5 space-y-3">
          <p className="text-xs text-[#888] mb-1">Summary</p>
          {([
            ['Principal',          principal],
            ['Max per transaction', `₹ ${maxTx}`],
            ['Auto-approve below',  `₹ ${autoApprove}`],
            ['Anomaly threshold',   `${maxDiscount}%`],
          ] as [string, string][]).map(([k, v]) => (
            <div key={k} className="flex justify-between text-sm">
              <span className="text-[#888]">{k}</span>
              <span className="text-white font-medium">{v}</span>
            </div>
          ))}
        </div>

        {error && (
          <p className="text-sm text-red-400 bg-red-950/60 border border-red-800 rounded-lg px-4 py-3">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 text-sm font-semibold bg-white text-black rounded-lg hover:bg-[#e5e5e5] disabled:bg-[#333] disabled:text-[#666] transition-colors duration-150"
        >
          {loading ? 'Signing mandate…' : 'Issue & Sign Mandate'}
        </button>
      </form>

      {createdId && (
        <div className="mt-8 rounded-lg border border-[#2a2a2a] bg-[#151515] p-5">
          <p className="text-xs text-[#888] uppercase tracking-wider mb-2">Mandate issued</p>
          <p className="font-mono text-sm text-white break-all leading-relaxed">{createdId}</p>
          <p className="text-xs text-[#666] mt-3">Switching to Negotiate tab…</p>
        </div>
      )}
    </div>
  )
}
