// types.ts — data structures for the Buyer Agent UI
export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

export interface WireEvent {
  id: string;
  timestamp: number;
  direction: "request" | "response";
  method: HttpMethod;
  path: string;
  status?: number;
  latencyMs?: number;
  signed: boolean;
  headers: Record<string, string>;
  body?: unknown;
  note?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  timestamp: number;
}

export type SessionStatus =
  | "idle"
  | "connecting"
  | "negotiating"
  | "closed_accepted"
  | "closed_rejected"
  | "error";

export interface AgentSessionState {
  status: SessionStatus;
  messages: ChatMessage[];
  wire: WireEvent[];
}
