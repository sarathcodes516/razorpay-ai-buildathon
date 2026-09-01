import React from 'react';
import { Cart, AuditEntry } from '../types/api';
import { ShieldAlert, CheckCircle, XCircle } from 'lucide-react';

interface Props { cart: Cart; audit: AuditEntry; onApprove: () => void; onReject: () => void; }

export default function ApprovalModal({ cart, audit, onApprove, onReject }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 border-t-4 border-red-500">
        <div className="flex items-center gap-3 mb-4 text-red-600">
          <ShieldAlert className="w-6 h-6" />
          <h2 className="text-lg font-bold">Mandate Limit Exceeded</h2>
        </div>
        <p className="text-sm text-gray-600 mb-4">Your AI agent wants to authorize a payment that exceeds your auto-approve limits.</p>
        <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 mb-4 text-sm font-mono">
          <p className="text-gray-500 text-xs uppercase mb-1">Failed Rule</p>
          <p className="text-red-600 font-bold">{audit.rule}</p>
          <p className="text-gray-800 mt-1">{audit.evaluated}</p>
        </div>
        <div className="border-t border-gray-200 pt-4 mb-6 flex justify-between font-bold text-lg">
          <span>Requested Amount:</span><span>₹{cart.final_amount.toFixed(2)}</span>
        </div>
        <div className="flex gap-3">
          <button onClick={onReject} className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg border border-gray-300 text-gray-700 font-semibold hover:bg-gray-50"><XCircle className="w-5 h-5" /> Deny</button>
          <button onClick={onApprove} className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700"><CheckCircle className="w-5 h-5" /> Approve</button>
        </div>
      </div>
    </div>
  );
}
