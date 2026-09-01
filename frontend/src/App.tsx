import React, { useEffect, useState, useRef } from 'react';
import Navbar from './components/Navbar';
import ProductGrid from './components/ProductGrid';
import ApprovalModal from './components/ApprovalModal';
import AgentGateway from './components/AgentGateway';
import MandateConfigurator from './components/MandateConfigurator';
import MerchantConfigPanel from './components/MerchantConfigPanel';
import { fetchCatalog, sendChatMessage, recoverPayment } from './api/client';
import { MessageSquare, Send, Bot, Activity, X } from 'lucide-react';
import { ChatResponse, AuditEntry } from './types/api';

export default function App() {
  const [catalog, setCatalog] = useState([]);
  const [mandateId, setMandateId] = useState("");
  const [activeTab, setActiveTab] = useState<'store' | 'gateway' | 'mandate' | 'merchant'>('mandate');

  // Chat state
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{role: string, text: string}[]>([{ role: 'agent', text: "Hey! I'm your AI concierge. Looking for gear?" }]);
  const [loading, setLoading] = useState(false);
  const [pendingResponse, setPendingResponse] = useState<ChatResponse | null>(null);

  // Audit trail state
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fetchCatalog().then(setCatalog); }, []);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !mandateId) return alert("Please enter a Mandate ID (from the terminal) and a message.");
    const userText = input;
    setInput("");
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setLoading(true);

    try {
      const res = await sendChatMessage(mandateId, userText);
      setAuditLogs(prev => [...prev, res.audit_trail]);
      if (res.action === "ESCALATE") {
        setPendingResponse(res);
      } else {
        setMessages(prev => [...prev, { role: 'agent', text: res.agent_message }]);
        if (res.action === "EXECUTE" && userText.toLowerCase().includes("fail")) {
          handleFailure("failure@razorpay declined the test transaction");
        }
      }
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'agent', text: `Error: ${e.message}` }]);
    }
    setLoading(false);
  };

  const handleFailure = async (reason: string) => {
    setMessages(prev => [...prev, { role: 'system', text: `[SYSTEM] Payment Failed: ${reason}` }]);
    setLoading(true);
    const recovery = await recoverPayment(reason);
    setMessages(prev => [...prev, { role: 'agent', text: recovery.agent_message }]);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-white pb-20">
      <Navbar />

      {/* TrustRail Global Header with tab switcher */}
      <div className="bg-gray-900 text-white p-2 flex flex-col sm:flex-row justify-between items-center px-6 z-30 relative gap-4">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-mono text-gray-300 font-bold">TRUSTRAIL PROTOCOL</span>
          <input
            type="text"
            placeholder="Paste Mandate ID (man_...)"
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1 w-48 sm:w-64 text-white focus:outline-none focus:border-red-500 font-mono text-xs"
            value={mandateId}
            onChange={e => setMandateId(e.target.value)}
          />
        </div>

        {/* Face switcher */}
        <div className="flex bg-gray-800 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('merchant')}
            className="px-4 py-1.5 text-xs font-bold rounded-md transition-colors"
            style={{ backgroundColor: activeTab === 'merchant' ? '#0E54CD' : 'transparent', color: activeTab === 'merchant' ? 'white' : '#9ca3af' }}
          >
            Merchant Config
          </button>
          <button
            onClick={() => setActiveTab('mandate')}
            className="px-4 py-1.5 text-xs font-bold rounded-md transition-colors"
            style={{ backgroundColor: activeTab === 'mandate' ? '#48D08C' : 'transparent', color: activeTab === 'mandate' ? 'white' : '#9ca3af' }}
          >
            Issue Mandate
          </button>
          <button
            onClick={() => setActiveTab('store')}
            className={`px-4 py-1.5 text-xs font-bold rounded-md transition-colors ${activeTab === 'store' ? 'bg-white text-black' : 'text-gray-400 hover:text-white'}`}
          >
            B2C Storefront
          </button>
          <button
            onClick={() => setActiveTab('gateway')}
            className="px-4 py-1.5 text-xs font-bold rounded-md transition-colors"
            style={{ backgroundColor: activeTab === 'gateway' ? '#0E54CD' : 'transparent', color: activeTab === 'gateway' ? 'white' : '#9ca3af' }}
          >
            B2B Agent Gateway
          </button>
        </div>
      </div>

      {/* Render active face */}
      {activeTab === 'store' ? (
        <>
          <ProductGrid catalog={catalog} />

          {/* Live Audit Trail — floating button + panel */}
          <div className="fixed bottom-6 left-6 z-50">
            {!auditOpen ? (
              <button
                onClick={() => setAuditOpen(true)}
                className="relative bg-gray-900 text-white p-4 rounded-full shadow-2xl hover:bg-gray-700 transition-colors"
              >
                <Activity className="w-6 h-6" />
                {auditLogs.length > 0 && (
                  <span className="absolute -top-1 -right-1 bg-red-600 text-white text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center">
                    {auditLogs.length}
                  </span>
                )}
              </button>
            ) : (
              <div className="bg-white rounded-2xl shadow-2xl w-[420px] max-h-[600px] flex flex-col border border-gray-200 overflow-hidden">
                <div className="bg-gray-900 text-white px-5 py-4 flex justify-between items-center flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <Activity className="w-5 h-5 text-red-400" />
                    <span className="font-bold tracking-wide">Live Audit Trail</span>
                    <span className="bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full ml-1">
                      {auditLogs.length} decisions
                    </span>
                  </div>
                  <X className="w-5 h-5 cursor-pointer hover:text-gray-300" onClick={() => setAuditOpen(false)} />
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                  {auditLogs.length === 0 ? (
                    <p className="text-sm text-gray-400 italic text-center py-8">Awaiting AI decisions...</p>
                  ) : (
                    auditLogs.map((log, i) => (
                      <div key={i} className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm">
                        <div className="flex items-center justify-between px-3 py-2 bg-gray-100 border-b border-gray-200">
                          <span className="text-xs font-mono text-gray-500">[{new Date().toLocaleTimeString()}]</span>
                          <span className="text-xs font-bold text-gray-500">Decision #{i + 1}</span>
                        </div>
                        <div className="p-3 space-y-3">
                          <div>
                            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Action Taken</p>
                            <p className={`text-sm font-black font-mono ${
                              log.action_taken.includes("EXECUTE") ? "text-green-600"
                              : log.action_taken.includes("REJECT") ? "text-red-700"
                              : "text-orange-500"
                            }`}>
                              {log.action_taken}
                            </p>
                          </div>
                          {log.rule && (
                            <div>
                              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Rule Evaluated</p>
                              <p className="text-xs font-mono text-gray-700 bg-gray-50 border border-gray-200 rounded px-2 py-1.5 break-all">
                                {log.rule}
                              </p>
                            </div>
                          )}
                          {log.evaluated && (
                            <div>
                              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">Result</p>
                              <p className={`text-xs font-mono font-bold px-2 py-1.5 rounded border break-all ${
                                log.evaluated.includes("PASS")
                                  ? "bg-green-50 border-green-200 text-green-700"
                                  : "bg-red-50 border-red-200 text-red-700"
                              }`}>
                                {log.evaluated}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* AI Concierge Chat */}
          <div className="fixed bottom-6 right-6 z-50">
            {!isOpen ? (
              <button onClick={() => setIsOpen(true)} className="bg-red-600 text-white p-4 rounded-full shadow-2xl hover:bg-red-700 transition-colors">
                <MessageSquare className="w-6 h-6" />
              </button>
            ) : (
              <div className="bg-white rounded-2xl shadow-2xl w-[380px] h-[500px] flex flex-col border border-gray-200 overflow-hidden">
                <div className="bg-red-600 text-white p-4 flex justify-between items-center">
                  <div className="flex items-center gap-2"><Bot className="w-5 h-5"/><span className="font-bold">AI Concierge</span></div>
                  <X className="w-5 h-5 cursor-pointer" onClick={() => setIsOpen(false)} />
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                  {messages.map((m, i) => (
                    <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      {m.role === 'agent' && <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center text-red-600 mt-1"><Bot className="w-4 h-4"/></div>}
                      <div className={`p-3 rounded-xl max-w-[80%] text-sm ${m.role === 'user' ? 'bg-black text-white rounded-br-none' : m.role === 'system' ? 'bg-red-100 text-red-800 border border-red-200 w-full' : 'bg-white border border-gray-200 rounded-bl-none text-gray-800 shadow-sm'}`}>{m.text}</div>
                    </div>
                  ))}
                  {loading && <div className="text-gray-400 text-xs flex items-center gap-1"><Activity className="w-3 h-3 animate-spin"/> Agent is thinking...</div>}
                  <div ref={chatEndRef} />
                </div>
                <div className="p-3 bg-white border-t border-gray-200 flex gap-2">
                  <input type="text" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSend()} placeholder="I need gear for a trek..." className="flex-1 border border-gray-300 rounded-full px-4 py-2 text-sm focus:outline-none focus:border-red-500" />
                  <button onClick={handleSend} className="bg-black text-white p-2.5 rounded-full hover:bg-gray-800"><Send className="w-4 h-4" /></button>
                </div>
              </div>
            )}
          </div>

          {pendingResponse && (
            <ApprovalModal
              cart={pendingResponse.cart}
              audit={pendingResponse.audit_trail}
              onApprove={() => {
                setMessages(prev => [...prev, { role: 'agent', text: pendingResponse.agent_message + "\n\n(Approved by human - Executing Order)" }]);
                setPendingResponse(null);
              }}
              onReject={() => {
                setMessages(prev => [...prev, { role: 'system', text: "Purchase denied by human." }]);
                setPendingResponse(null);
              }}
            />
          )}
        </>
      ) : activeTab === 'gateway' ? (
        <AgentGateway mandateId={mandateId} />
      ) : activeTab === 'merchant' ? (
        <MerchantConfigPanel />
      ) : (
        <MandateConfigurator onMandateCreated={(id) => { setMandateId(id); setActiveTab('store'); }} />
      )}
    </div>
  );
}
