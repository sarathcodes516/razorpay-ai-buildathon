export interface CartItem { sku: string; qty: number; price: number; category: string; }
export interface Cart { cart_id: string; mandate_id: string; items: CartItem[]; subtotal: number; discount_pct: number; final_amount: number; }
export interface AuditEntry { step: string; rule?: string; evaluated?: string; action_taken: string; }
export interface ChatResponse { agent_message: string; cart: Cart; action: "EXECUTE" | "ESCALATE" | "REJECT"; audit_trail: AuditEntry; razorpay_order?: any; error?: string; }

export interface NegotiationTurn {
  role: 'buyer' | 'merchant';
  data: {
    thought_process: string;
    action: string;
    message: string;
    requested_discount_pct?: number;
    offered_discount_pct?: number;
  };
}

export interface NegotiationResponse {
  transcript: NegotiationTurn[];
  final_cart: Cart | null;
  action: "EXECUTE" | "ESCALATE" | "REJECT";
  audit_trail: AuditEntry;
  razorpay_order?: any;
  error?: string;
}
