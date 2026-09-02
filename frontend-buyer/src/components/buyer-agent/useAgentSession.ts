// useAgentSession.ts — API hook driving the buyer agent negotiation stream
import { useCallback, useRef, useState } from "react";
import type { AgentSessionState, ChatMessage, WireEvent } from "./types";

const API_BASE = import.meta.env.VITE_BUYER_AGENT_API ?? "http://localhost:8001";
const makeId = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 10)}`;

/**
 * Expects POST /api/buyer-agent/run to stream newline-delimited JSON, one
 * event per line, as the negotiation happens:
 *   {"type":"chat","role":"agent"|"system","content":"..."}
 *   {"type":"wire", ...WireEvent fields}
 *   {"type":"status","status":"negotiating"|"closed_accepted"|...}
 */
export function useAgentSession() {
  const [state, setState] = useState<AgentSessionState>({
    status: "idle",
    messages: [],
    wire: [],
  });
  const abortRef = useRef<AbortController | null>(null);

  const pushChat = (role: ChatMessage["role"], content: string) =>
    setState((s) => ({
      ...s,
      messages: [
        ...s.messages,
        { id: makeId("msg"), role, content, timestamp: Date.now() },
      ],
    }));

  const pushWire = (event: Omit<WireEvent, "id" | "timestamp">) =>
    setState((s) => ({
      ...s,
      wire: [
        ...s.wire,
        { ...event, id: makeId("wire"), timestamp: Date.now() },
      ],
    }));

  const start = useCallback(
    async (merchantUrl: string, task: string, mandateId: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({ status: "connecting", messages: [], wire: [] });
      pushChat("user", task);
      pushChat("system", `Discovering ${merchantUrl}…`);

      try {
        const res = await fetch(`${API_BASE}/api/buyer-agent/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            merchant_url: merchantUrl,
            task,
            mandate_id: mandateId,
          }),
          signal: controller.signal,
        });

        if (!res.body) throw new Error("no stream body");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        setState((s) => ({ ...s, status: "negotiating" }));

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.trim()) continue;
            const evt = JSON.parse(line);
            if (evt.type === "chat") pushChat(evt.role, evt.content);
            if (evt.type === "wire") pushWire(evt);
            if (evt.type === "status")
              setState((s) => ({ ...s, status: evt.status }));
          }
        }

        // Flush any remaining buffered content that arrived without a trailing newline
        if (buffer.trim()) {
          try {
            const evt = JSON.parse(buffer);
            if (evt.type === "chat") pushChat(evt.role, evt.content);
            if (evt.type === "wire") pushWire(evt);
            if (evt.type === "status")
              setState((s) => ({ ...s, status: evt.status }));
          } catch {
            // Partial/malformed final chunk — discard safely
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          pushChat(
            "system",
            `Connection lost: ${(err as Error).message}`
          );
          setState((s) => ({ ...s, status: "error" }));
        }
      }
    },
    []
  );

  return { state, start, stop: () => abortRef.current?.abort() };
}
