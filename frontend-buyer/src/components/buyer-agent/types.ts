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

export interface CatalogProof {
  ok: boolean;
  item_count: number;
  signature: string;
}

export interface SettlementProof {
  execution: {
    razorpay_order_id?: string;
    receipt?: string;
    amount?: number;
    sku?: string;
    qty?: number;
    discount_pct?: number;
    settlement_signature?: string;
  };
  bounds_action?: string;
  mandate_ceiling?: number;
}

export interface AgentSessionState {
  status: SessionStatus;
  messages: ChatMessage[];
  wire: WireEvent[];
  settlement?: SettlementProof | null;
  catalog?: CatalogProof | null;
}
