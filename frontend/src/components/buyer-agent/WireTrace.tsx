// WireTrace.tsx
import { useEffect, useRef, useState } from "react";
import type { WireEvent } from "./types";
import { colors } from "./tokens";

function statusTone(status?: number) {
  if (status === undefined) return colors.accent;
  if (status < 300) return colors.success;
  return colors.error;
}

function WireRow({ event }: { event: WireEvent }) {
  const [open, setOpen] = useState(false);
  const inFlight = event.direction === "request";

  return (
    <div style={{ borderBottom: `1px solid ${colors.cream}12` }}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-white/5"
      >
        <span
          className="text-[10px] tabular-nums w-16 shrink-0"
          style={{ color: `${colors.cream}55` }}
        >
          {new Date(event.timestamp).toLocaleTimeString("en-IN", { hour12: false })}
        </span>
        <span
          className="text-xs font-semibold w-12 shrink-0"
          style={{ color: `${colors.cream}CC` }}
        >
          {event.method}
        </span>
        <span className="text-xs truncate flex-1" style={{ color: `${colors.cream}D9` }}>
          {event.path}
        </span>
        {event.signed && (
          <span
            className="text-[9px] rounded-sm px-1 shrink-0 border"
            style={{ color: colors.success, borderColor: `${colors.success}55` }}
          >
            signed
          </span>
        )}
        <span
          className={`text-xs font-mono w-14 text-right shrink-0 ${
            inFlight ? "animate-pulse" : ""
          }`}
          style={{ color: statusTone(event.status) }}
        >
          {inFlight ? "···" : event.status}
        </span>
        {event.latencyMs !== undefined && (
          <span
            className="text-[10px] w-14 text-right shrink-0 tabular-nums"
            style={{ color: `${colors.cream}55` }}
          >
            {event.latencyMs}ms
          </span>
        )}
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1" style={{ backgroundColor: `${colors.cream}08` }}>
          {event.note && (
            <p className="text-xs mb-2" style={{ color: colors.error }}>
              {event.note}
            </p>
          )}
          <pre
            className="text-[11px] leading-relaxed overflow-x-auto whitespace-pre-wrap"
            style={{ color: `${colors.cream}B0` }}
          >
            {JSON.stringify({ headers: event.headers, body: event.body }, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function WireTrace({ events }: { events: WireEvent[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [events.length]);

  return (
    <div className="h-full flex flex-col" style={{ backgroundColor: colors.charcoal }}>
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: `1px solid ${colors.cream}18` }}
      >
        <span className="text-[13px]" style={{ color: `${colors.cream}CC` }}>
          Wire
        </span>
        <span className="text-[10px] font-mono" style={{ color: `${colors.cream}55` }}>
          {events.length} calls
        </span>
      </div>
      <div className="flex-1 overflow-y-auto font-mono">
        {events.length === 0 ? (
          <p
            className="px-4 py-6 text-xs font-sans"
            style={{ color: `${colors.cream}55` }}
          >
            Nothing on the wire yet — give your agent a task to watch it negotiate live.
          </p>
        ) : (
          events.map((e) => <WireRow key={e.id} event={e} />)
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
