// ChatPanel.tsx
import { useEffect, useRef, useState } from 'react'
import type { AgentSessionState, ChatMessage, SessionStatus } from './types'

const inputCls = 'w-full px-3.5 py-2.5 text-sm bg-[#1a1a1a] border border-[#333] text-white ' +
  'placeholder-[#555] focus:border-[#666] focus:outline-none rounded-lg transition-colors'

function Bubble({ message }: { message: ChatMessage }) {
  const isUser   = message.role === 'user'
  const isSystem = message.role === 'system'
  return (
    <div className={`px-4 py-1.5 flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      {isUser ? (
        <div className="max-w-[75%] bg-[#1a1a1a] border border-[#333] rounded-xl px-4 py-2.5 text-sm text-[#e5e5e5]">
          {message.content}
        </div>
      ) : (
        <div className="max-w-[85%]">
          <p className={`text-[10px] font-semibold uppercase tracking-widest mb-1 ${
            isSystem ? 'text-[#555]' : 'text-[#888]'
          }`}>{isSystem ? 'system' : 'agent'}</p>
          <p className={`text-sm leading-relaxed ${
            isSystem ? 'text-[#666] italic' : 'text-[#ccc]'
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
      <span className="text-xs text-[#888]">{text}</span>
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
    <div className="h-full flex flex-col bg-[#0d0d0d]">
      <div className="flex-none px-4 py-3.5 border-b border-[#222]">
        <p className="text-xs font-medium text-[#888] uppercase tracking-wide">Agent-to-Agent Wire</p>
      </div>

      {!started ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
          <div>
            <label className="block text-xs font-medium text-[#aaa] uppercase tracking-wide mb-1.5">Merchant URL</label>
            <input value={merchantUrl} onChange={e => setMerchantUrl(e.target.value)}
              placeholder="http://localhost:8001" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#aaa] uppercase tracking-wide mb-1.5">Mandate ID</label>
            <input value={mandateId} onChange={e => setMandateId(e.target.value)}
              placeholder="man_..." className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#aaa] uppercase tracking-wide mb-1.5">Task</label>
            <textarea value={task} onChange={e => setTask(e.target.value)} rows={3}
              placeholder="Get 15 graphic tees for a crew event, keep it under budget."
              className={`${inputCls} resize-none`} />
          </div>
          <button onClick={submit}
            className="w-full py-2.5 text-sm font-semibold bg-white text-black rounded-lg hover:bg-[#e5e5e5] transition-colors">
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
          <div className="flex-none px-4 py-3 border-t border-[#222]">
            <button
              onClick={() => onStart(merchantUrl, task, mandateId)}
              disabled={state.status === 'negotiating' || state.status === 'connecting'}
              className="w-full py-2 text-xs font-medium border border-[#333] text-[#888] rounded-lg hover:border-[#555] hover:text-[#ccc] disabled:opacity-30 transition-colors"
            >Run Again</button>
          </div>
        </>
      )}
    </div>
  )
}
