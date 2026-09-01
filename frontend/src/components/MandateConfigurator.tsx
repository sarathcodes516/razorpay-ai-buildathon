import React, { useState } from 'react';
import axios from 'axios';
import { ShieldCheck, Key } from 'lucide-react';

const BUYER_GREEN = '#48D08C';

export default function MandateConfigurator({ onMandateCreated }: { onMandateCreated: (id: string) => void }) {
  const [principal, setPrincipal] = useState("Corporate Buyer Alpha");
  const [maxTx, setMaxTx] = useState(5000);
  const [autoApprove, setAutoApprove] = useState(2500);
  const [maxDiscount, setMaxDiscount] = useState(15);
  const [createdId, setCreatedId] = useState("");
  const [loading, setLoading] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await axios.post('http://localhost:8001/api/mandate/dynamic', {
        principal,
        max_per_transaction: Number(maxTx),
        max_total_spend_today: 15000,
        allowed_categories: ["apparel", "accessories"],
        auto_approve_below: Number(autoApprove),
        max_discount_agent_can_accept_pct: Number(maxDiscount)
      });
      setCreatedId(res.data.mandate_id);
      onMandateCreated(res.data.mandate_id);
    } catch (err) {
      alert("Failed to issue mandate");
    }
    setLoading(false);
  };

  return (
    <div className="max-w-xl mx-auto bg-white rounded-2xl p-8 shadow-sm my-10" style={{ border: `2px solid ${BUYER_GREEN}` }}>
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 rounded-xl" style={{ backgroundColor: `${BUYER_GREEN}20`, color: BUYER_GREEN }}>
          <ShieldCheck className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-black text-gray-900">UAP Spend Mandate Issuance</h2>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase text-white" style={{ backgroundColor: BUYER_GREEN }}>
              Buyer Side
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">Cryptographically bind your agent's spending authority</p>
        </div>
      </div>

      <form onSubmit={handleCreate} className="space-y-4">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">Principal / Entity Name</label>
          <input
            type="text"
            value={principal}
            onChange={e => setPrincipal(e.target.value)}
            className="w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm focus:outline-none"
            style={{ '--tw-ring-color': BUYER_GREEN } as React.CSSProperties}
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">Max Per Transaction (₹)</label>
            <input
              type="number"
              value={maxTx}
              onChange={e => setMaxTx(Number(e.target.value))}
              className="w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm font-mono focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">Auto-Approve Below (₹)</label>
            <input
              type="number"
              value={autoApprove}
              onChange={e => setAutoApprove(Number(e.target.value))}
              className="w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm font-mono focus:outline-none"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">
            Anomaly Discount Threshold (%) — Escalate if offer exceeds this
          </label>
          <input
            type="number"
            value={maxDiscount}
            onChange={e => setMaxDiscount(Number(e.target.value))}
            className="w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm font-mono focus:outline-none"
          />
          <p className="text-[10px] text-gray-400 mt-1">
            If the merchant offers more than this %, the bounds engine escalates to human review — not a negotiation floor, a fraud tripwire.
          </p>
        </div>

        {/* Preview block */}
        <div className="rounded-lg p-3 text-xs font-mono space-y-1" style={{ backgroundColor: `${BUYER_GREEN}10`, border: `1px solid ${BUYER_GREEN}40` }}>
          <div className="font-bold" style={{ color: BUYER_GREEN }}>spend_mandate:</div>
          <div className="pl-2 text-gray-600">max_per_transaction: <span className="font-bold" style={{ color: BUYER_GREEN }}>₹{maxTx.toLocaleString()}</span></div>
          <div className="pl-2 text-gray-600">auto_approve_below: <span className="font-bold" style={{ color: BUYER_GREEN }}>₹{autoApprove.toLocaleString()}</span></div>
          <div className="pl-2 text-gray-600">anomaly_threshold: <span className="font-bold" style={{ color: BUYER_GREEN }}>{maxDiscount}%</span></div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full text-white font-bold py-3.5 rounded-xl transition-all shadow-md disabled:opacity-50"
          style={{ backgroundColor: BUYER_GREEN }}
        >
          {loading ? "Signing..." : "Sign & Issue Dynamic Mandate"}
        </button>
      </form>

      {createdId && (
        <div className="mt-6 p-4 rounded-xl flex items-center justify-between" style={{ backgroundColor: `${BUYER_GREEN}15`, border: `1px solid ${BUYER_GREEN}50` }}>
          <div className="flex items-center gap-2 text-xs font-mono font-bold" style={{ color: BUYER_GREEN }}>
            <Key className="w-4 h-4" /> Issued ID: {createdId}
          </div>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase text-white" style={{ backgroundColor: BUYER_GREEN }}>
            Active
          </span>
        </div>
      )}
    </div>
  );
}
