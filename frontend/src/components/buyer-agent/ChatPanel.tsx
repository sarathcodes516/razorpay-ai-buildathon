// ChatPanel.tsx
import { useState } from "react";
import type { AgentSessionState, ChatMessage, SessionStatus } from "./types";
import { colors } from "./tokens";

function Bubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end px-6 py-1.5">
        <div
          className="max-w-[75%] rounded-2xl rounded-br-sm px-4 py-2.5 text-[15px] leading-relaxed"
          style={{ backgroundColor: `${colors.ink}0D`, color: colors.ink }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  const isSystem = message.role === "system";
  return (
    <div className="px-6 py-1.5">
      <div className="flex items-baseline gap-2 mb-1">
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ backgroundColor: isSystem ? `${colors.ink}40` : colors.accent }}
        />
        <span className="text-xs" style={{ color: `${colors.ink}66` }}>
          {isSystem ? "system" : "your agent"}
        </span>
      </div>
      <p
        className="text-[15px] leading-relaxed max-w-[85%]"
        style={{
          color: isSystem ? `${colors.ink}80` : colors.ink,
          fontStyle: isSystem ? "italic" : "normal",
        }}
      >
        {message.content}
      </p>
    </div>
  );
}

function StatusLine({ status }: { status: SessionStatus }) {
  const copy: Record<SessionStatus, string> = {
    idle: "",
    connecting: "Reaching the merchant…",
    negotiating: "Negotiating…",
    closed_accepted: "Deal reached.",
    closed_rejected: "No deal — the merchant declined.",
    error: "Something went wrong on the wire.",
  };

  if (!copy[status]) return null;

  return (
    <div className="px-6 py-2 flex items-center gap-2">
      {status === "negotiating" && (
        <span className="flex gap-0.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1 h-1 rounded-full animate-pulse"
              style={{ backgroundColor: colors.accent, animationDelay: `${i * 150}ms` }}
            />
          ))}
        </span>
      )}
      <span className="text-xs" style={{ color: `${colors.ink}66` }}>
        {copy[status]}
      </span>
    </div>
  );
}

export function ChatPanel({
  state,
  onStart,
}: {
  state: AgentSessionState;
  onStart: (url: string, task: string, mandateId: string) => void;
}) {
  const [merchantUrl, setMerchantUrl] = useState("");
  const [mandateId, setMandateId] = useState("");
  const [task, setTask] = useState("");

  const started = state.messages.length > 0;

  const submit = () =>
    merchantUrl.trim() &&
    task.trim() &&
    mandateId.trim() &&
    onStart(merchantUrl.trim(), task.trim(), mandateId.trim());

  return (
    <div className="h-full flex flex-col" style={{ backgroundColor: colors.cream }}>
      <div className="px-6 py-4" style={{ borderBottom: `1px solid ${colors.ink}14` }}>
        <h1 className="text-[15px] font-medium" style={{ color: colors.ink }}>
          Buyer agent
        </h1>
        <p className="text-xs mt-0.5" style={{ color: `${colors.ink}66` }}>
          Give it a store and a task. It carries its own mandate and negotiates on its own.
        </p>
      </div>

      {!started ? (
        <div className="flex-1 flex flex-col justify-center px-6 gap-3 max-w-md">
          <label className="text-xs" style={{ color: `${colors.ink}80` }}>
            Store URL
          </label>
          <input
            value={merchantUrl}
            onChange={(e) => setMerchantUrl(e.target.value)}
            placeholder="https://soledstole.example.com"
            className="rounded-lg px-3 py-2 text-sm outline-none border"
            style={{ borderColor: `${colors.ink}20`, color: colors.ink }}
          />

          <label className="text-xs mt-2" style={{ color: `${colors.ink}80` }}>
            Your mandate ID
          </label>
          <input
            value={mandateId}
            onChange={(e) => setMandateId(e.target.value)}
            placeholder="man_1788273383"
            className="rounded-lg px-3 py-2 text-sm outline-none border font-mono"
            style={{ borderColor: `${colors.ink}20`, color: colors.ink }}
          />

          <label className="text-xs mt-2" style={{ color: `${colors.ink}80` }}>
            Task
          </label>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={3}
            placeholder="Get me 15 graphic tees for a crew event, keep it under budget."
            className="rounded-lg px-3 py-2 text-sm outline-none border resize-none"
            style={{ borderColor: `${colors.ink}20`, color: colors.ink }}
          />

          <button
            onClick={submit}
            className="mt-2 rounded-lg py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: colors.accent }}
          >
            Send agent
          </button>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto py-3">
            {state.messages.map((m) => (
              <Bubble key={m.id} message={m} />
            ))}
            <StatusLine status={state.status} />
          </div>
          <div className="px-6 py-4" style={{ borderTop: `1px solid ${colors.ink}14` }}>
            <button
              onClick={() => onStart(merchantUrl, task, mandateId)}
              disabled={state.status === "negotiating" || state.status === "connecting"}
              className="w-full rounded-lg py-2.5 text-sm font-medium border disabled:opacity-40 transition-opacity"
              style={{ borderColor: `${colors.ink}20`, color: colors.ink }}
            >
              Run again
            </button>
          </div>
        </>
      )}
    </div>
  );
}
