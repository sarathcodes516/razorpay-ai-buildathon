// ChatPanel.tsx
import { useEffect, useRef, useState } from 'react'
import type { AgentSessionState, ChatMessage, SessionStatus } from './types'

const inputCls = 'w-full px-3.5 py-2.5 text-sm bg-[#262626] border border-[#3a3a3a] text-white ' +
  'placeholder-[#888888] focus:border-[#666666] focus:outline-none rounded-lg transition-colors'

function Bubble({ message }: { message: ChatMessage }) {
  const isUser   = message.role === 'user'
  const isSystem = message.role === 'system'
  // Render an indented trust-layer block when the system feed is describing
  // the signed-catalog handshake. We match the leading "Trust layer:" tag
  // emitted by the backend runner.
  const isTrustLine = isSystem && message.content.trim().startsWith('Trust layer')
  const isTrustSub  = isSystem && (
    message.content.includes('Payload signed by') ||
    message.content.includes('Ed25519 Signature') ||
    message.content.includes('Signature verification')
  )
  return (
    <div className={`px-4 py-1.5 flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      {isUser ? (
        <div className="max-w-[75%] bg-ink-800 border border-ink-700 rounded-xl px-4 py-2.5 text-sm text-ink-50">
          {message.content}
        </div>
      ) : (
        <div className={`max-w-[85%] ${isTrustLine ? 'border-l-2 border-indigo-500/40 bg-indigo-950/15 rounded-r-lg pl-3 py-1' : ''} ${isTrustSub ? 'border-l-2 border-indigo-500/20 pl-3' : ''}`}>
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-1 ${
            isTrustLine ? 'text-indigo-400'
            : isTrustSub  ? 'text-indigo-300/80'
            : isSystem    ? 'text-ink-500'
                          : 'text-ink-300'
          }`}>{isTrustLine ? 'Trust Layer' : isTrustSub ? '' : isSystem ? 'system' : 'agent'}</p>
          <p className={`text-sm leading-relaxed ${
            isTrustLine ? 'text-indigo-200 font-mono text-[12px]'
            : isTrustSub  ? 'text-indigo-300/80 font-mono text-[11px]'
            : isSystem    ? 'text-ink-400 italic'
                          : 'text-ink-100'
          }`}>{message.content}</p>
        </div>
      )}
    </div>
  )
}

function StatusLine({ status }: { status: SessionStatus }) {
  const labels: Partial<Record<SessionStatus, string>> = {
    connecting:      'Connecting...',
    negotiating:     'Negotiating...',
    closed_accepted: 'Deal reached.',
    closed_rejected: 'No deal.',
    error:           'Error on the wire.',
  }
  const text = labels[status]
  if (!text) return null
  return (
    <div className="px-4 py-2 flex items-center gap-2">
      {status === 'negotiating' && (
        <span className="flex gap-0.5">
          {[0, 1, 2].map(i => (
            <span key={i} className="w-1 h-1 rounded-full bg-[#666] animate-pulse"
              style={{ animationDelay: `${i * 150}ms` }} />
          ))}
        </span>
      )}
      <span className="text-xs text-ink-300">{text}</span>
    </div>
  )
}

export function ChatPanel({
  state, onStart, defaultMandateId,
}: {
  state: AgentSessionState
  onStart: (url: string, task: string, mandateId: string) => void
  defaultMandateId?: string
}) {
  const [merchantUrl, setMerchantUrl] = useState('http://localhost:8001')
  const [mandateId,   setMandateId]   = useState(defaultMandateId || '')
  const [task,        setTask]        = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (defaultMandateId) setMandateId(defaultMandateId) }, [defaultMandateId])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [state.messages])

  const started = state.messages.length > 0
  const submit  = () =>
    merchantUrl.trim() && task.trim() && mandateId.trim() &&
    onStart(merchantUrl.trim(), task.trim(), mandateId.trim())

  return (
    <div className="h-full flex flex-col bg-ink-900">
      <div className="flex-none px-4 py-3.5 border-b border-ink-700">
        <p className="text-xs font-medium text-ink-300 uppercase tracking-wide">Agent-to-Agent Wire</p>
      </div>

      {!started ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
          <div>
            <label className="block text-xs font-medium text-ink-200 uppercase tracking-wide mb-1.5">Merchant URL</label>
            <input value={merchantUrl} onChange={e => setMerchantUrl(e.target.value)}
              placeholder="http://localhost:8001" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-200 uppercase tracking-wide mb-1.5">Mandate ID</label>
            <input value={mandateId} onChange={e => setMandateId(e.target.value)}
              placeholder="man_..." className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-200 uppercase tracking-wide mb-1.5">Task</label>
            <textarea value={task} onChange={e => setTask(e.target.value)} rows={3}
              placeholder="Get 15 graphic tees for a crew event, keep it under budget."
              className={`${inputCls} resize-none`} />
          </div>
          <button onClick={submit}
            className="w-full py-2.5 text-sm font-semibold bg-[#6CE8AA] text-black rounded-lg hover:bg-[#5BD699] active:bg-[#4AC088] transition-colors">
            Start Negotiation
          </button>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto py-3">
            {state.messages.map(m => <Bubble key={m.id} message={m} />)}
            <StatusLine status={state.status} />
            <div ref={bottomRef} />
          </div>
          <div className="flex-none px-4 py-3 border-t border-ink-700">
            <button
              onClick={() => onStart(merchantUrl, task, mandateId)}
              disabled={state.status === 'negotiating' || state.status === 'connecting'}
              className="w-full py-2 text-xs font-medium border border-ink-700 text-ink-300 rounded-lg hover:border-ink-600 hover:text-ink-100 disabled:opacity-30 transition-colors"
            >Run Again</button>
          </div>
        </>
      )}
    </div>
  )
}
