import React, { useState } from 'react';
import { startNegotiation } from '../api/client';
import { NegotiationResponse } from '../types/api';
import { Activity, ShieldAlert, Cpu } from 'lucide-react';
import ApprovalModal from './ApprovalModal';

const MERCHANT_BLUE = '#0E54CD';
const BUYER_GREEN = '#48D08C';

export default function AgentGateway({ mandateId }: { mandateId: string }) {
  const [goal, setGoal] = useState("I need 15 Graphic Tees for a crew event. My budget is tight.");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<NegotiationResponse | null>(null);
  const [showModal, setShowModal] = useState(false);

  const runSimulation = async () => {
    if (!mandateId) return alert("Please enter a Mandate ID in the top bar.");
    setLoading(true);
    setResponse(null);
    try {
      const res = await startNegotiation(mandateId, goal);
      setResponse(res);
      if (res.action === "ESCALATE") setShowModal(true);
    } catch (e: any) {
      alert("Error: " + e.message);
    }
    setLoading(false);
  };

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <Cpu className="w-8 h-8" style={{ color: MERCHANT_BLUE }} />
        <div>
          <h2 className="text-2xl font-black tracking-tight text-gray-900">UAP/AP2 Agent Gateway</h2>
          <p className="text-sm text-gray-500">B2B Autonomous Procurement Interface</p>
        </div>
        {/* Legend */}
        <div className="ml-auto flex items-center gap-4 text-xs font-bold">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: BUYER_GREEN }}></span>
            <span style={{ color: BUYER_GREEN }}>Procurement AI (Buyer)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: MERCHANT_BLUE }}></span>
            <span style={{ color: MERCHANT_BLUE }}>Merchant AI (Seller)</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Col: Setup & Result */}
        <div className="space-y-6">
          {/* Buyer payload — green border */}
          <div className="bg-white rounded-xl p-5 shadow-sm" style={{ border: `1.5px solid ${BUYER_GREEN}` }}>
            <h3 className="font-bold text-sm uppercase tracking-wider mb-1" style={{ color: BUYER_GREEN }}>
              External Buyer Payload
            </h3>
            <p className="text-[10px] text-gray-400 mb-3">What the Procurement AI is instructed to achieve</p>
            <textarea
              className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none"
              rows={4}
              value={goal}
              onChange={e => setGoal(e.target.value)}
              style={{ borderColor: `${BUYER_GREEN}60` }}
            />
            <button
              onClick={runSimulation}
              disabled={loading}
              className="w-full mt-4 text-white font-bold py-3 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
              style={{ backgroundColor: MERCHANT_BLUE }}
            >
              {loading
                ? <><Activity className="w-5 h-5 animate-spin" /> Agents Negotiating...</>
                : "Initialize Autonomous Negotiation"}
            </button>
          </div>

          {/* Bounds Engine result */}
          {response && response.audit_trail && (
            <div className="bg-gray-900 rounded-xl p-5 shadow-lg text-white font-mono text-sm">
              <div className="flex items-center gap-2 text-gray-400 mb-3 pb-3 border-b border-gray-800">
                <ShieldAlert className="w-4 h-4" /> BOUNDS ENGINE EXECUTED
              </div>
              <div className="space-y-2">
                <div>
                  <span className="text-gray-500">Rule Evaluated:</span>
                  <p className="text-yellow-400 mt-1 break-all">{response.audit_trail.rule}</p>
                </div>
                <div>
                  <span className="text-gray-500">Result:</span>
                  <p className={`mt-1 break-all font-bold ${response.audit_trail.evaluated?.includes('PASS') ? 'text-green-400' : 'text-red-400'}`}>
                    {response.audit_trail.evaluated}
                  </p>
                </div>
                <div className="pt-2 border-t border-gray-800 flex justify-between items-center">
                  <span className="text-gray-500">Decision:</span>
                  <span className={`font-black text-base ${response.action === 'EXECUTE' ? 'text-green-400' : 'text-red-400'}`}>
                    {response.action}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Negotiated cart */}
          {response?.final_cart && (
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
              <h3 className="font-bold text-sm uppercase tracking-wider text-gray-700 mb-3">Negotiated Cart</h3>
              <div className="space-y-1 text-sm">
                {response.final_cart.items.map((item, i) => (
                  <div key={i} className="flex justify-between text-gray-700">
                    <span>{item.sku} × {item.qty}</span>
                    <span>₹{(item.price * item.qty).toLocaleString()}</span>
                  </div>
                ))}
                <div className="border-t border-gray-200 pt-2 mt-2 space-y-1">
                  <div className="flex justify-between text-gray-500"><span>Subtotal</span><span>₹{response.final_cart.subtotal.toLocaleString()}</span></div>
                  <div className="flex justify-between font-bold" style={{ color: BUYER_GREEN }}><span>Discount</span><span>-{response.final_cart.discount_pct}%</span></div>
                  <div className="flex justify-between font-black text-gray-900 text-base"><span>Final</span><span>₹{response.final_cart.final_amount.toLocaleString()}</span></div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Col: Live Protocol Transcript */}
        <div className="lg:col-span-2 bg-gray-50 border border-gray-200 rounded-xl p-1 shadow-inner h-[600px] overflow-hidden flex flex-col">
          <div className="bg-white border-b border-gray-200 px-4 py-3 flex justify-between items-center rounded-t-lg flex-shrink-0">
            <span className="font-bold text-sm text-gray-700 tracking-wide">PROTOCOL TRANSCRIPT</span>
            <span className="text-xs font-mono text-gray-400">auth: {mandateId || 'none'}</span>
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            {!response && !loading && (
              <div className="h-full flex items-center justify-center text-gray-400 italic text-sm">
                Awaiting connection from external agent...
              </div>
            )}
            {loading && (
              <div className="h-full flex flex-col items-center justify-center gap-3" style={{ color: MERCHANT_BLUE }}>
                <Activity className="w-8 h-8 animate-spin" />
                <p className="text-sm font-mono">Agents negotiating autonomously...</p>
              </div>
            )}

            {response?.transcript.map((turn, i) => {
              const isBuyer = turn.role === 'buyer';
              const color = isBuyer ? BUYER_GREEN : MERCHANT_BLUE;
              const discountKey = isBuyer ? turn.data.requested_discount_pct : turn.data.offered_discount_pct;
              const discountLabel = isBuyer ? 'req_discount' : 'offer_discount';

              return (
                <div key={i} className={`flex flex-col ${isBuyer ? 'items-start' : 'items-end'}`}>
                  <div className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color }}>
                    {isBuyer ? '🤖 Procurement AI' : '🏪 Merchant AI'}
                  </div>
                  <div
                    className="max-w-[85%] rounded-xl p-4 shadow-sm"
                    style={{
                      border: `1.5px solid ${color}30`,
                      backgroundColor: `${color}08`
                    }}
                  >
                    <p className="text-gray-800 text-sm mb-3">{turn.data.message}</p>
                    <div className="bg-gray-900 rounded p-3 font-mono text-xs text-gray-300">
                      <div className="text-gray-500 mb-1">// INTERNAL THOUGHT PROCESS</div>
                      <div className="mb-2 break-words" style={{ color: `${color}cc` }}>{turn.data.thought_process}</div>
                      <div>
                        <span className="text-gray-500">action: </span>
                        <span className="text-white font-bold">{turn.data.action}</span>
                      </div>
                      {discountKey !== undefined && (
                        <div>
                          <span className="text-gray-500">{discountLabel}: </span>
                          <span className="font-bold" style={{ color }}>{discountKey}%</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {showModal && response?.final_cart && (
        <ApprovalModal
          cart={response.final_cart}
          audit={response.audit_trail}
          onApprove={() => setShowModal(false)}
          onReject={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
