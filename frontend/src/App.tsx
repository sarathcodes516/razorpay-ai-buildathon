import React, { useEffect, useState, useRef } from 'react';
import Navbar from './components/Navbar';
import ProductGrid from './components/ProductGrid';
import MerchantConfigPanel from './components/MerchantConfigPanel';
import { fetchCatalog, sendChatMessage, recoverPayment, confirmPurchase } from './api/client';
import {
  MessageSquare, Send, Bot, Activity, X,
  CheckCircle, XCircle, ShoppingBag, Mic, Headphones,
} from 'lucide-react';
import { ChatResponse, AuditEntry, CartItem } from './types/api';

// Cart item shape for the live sidecar
interface LiveCartItem { sku: string; name: string; price: number; qty: number; }

export default function App() {
  const [catalog, setCatalog]           = useState([]);
  const [activeTab, setActiveTab]       = useState<'store' | 'merchant'>('store');
  const [isCartModalOpen, setIsCartModalOpen] = useState(false);

  // Widget state
  const [isOpen, setIsOpen]             = useState(false);
  const [isVoiceMode, setIsVoiceMode]   = useState(false);

  // Chat state
  const [input, setInput]               = useState('');
  const [messages, setMessages]         = useState<{ role: string; text: string; confirm?: ChatResponse }[]>([
    { role: 'agent', text: "Hey! I'm your AI concierge. Tell me what you're looking for." },
  ]);
  const [loading, setLoading]           = useState(false);
  const [liveCart, setLiveCart]         = useState<LiveCartItem[]>([]);
  const [history, setHistory]           = useState('');
  const [rzpOrder, setRzpOrder]         = useState<{ amount: number; currency: string; id: string; key_id: string } | null>(null);

  // Refs to prevent stale closures inside the WebSocket voice loop.
  // The silence-timer callback captures state at mic-open time; these refs
  // always hold the current value regardless of when they're read.
  const liveCartRef  = useRef<LiveCartItem[]>([]);
  const historyRef   = useRef('');

  useEffect(() => { liveCartRef.current = liveCart; },  [liveCart]);
  useEffect(() => { historyRef.current  = history;  },  [history]);

  // Voice / Deepgram state
  const [isListening, setIsListening]   = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const wsRef                           = useRef<WebSocket | null>(null);
  const mediaRecorderRef                = useRef<MediaRecorder | null>(null);
  const silenceTimerRef                 = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Audit trail state
  const [auditOpen, setAuditOpen]       = useState(false);
  const [auditLogs, setAuditLogs]       = useState<AuditEntry[]>([]);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fetchCatalog().then(setCatalog); }, []);
  useEffect(() => {
    // Pre-load voices so first TTS response isn't robotic
    window.speechSynthesis.getVoices();
  }, []);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, liveTranscript]);

  // ── Voice toggle ────────────────────────────────────────────────────────────
  const toggleVoice = async () => {
    if (isListening) {
      mediaRecorderRef.current?.stop();
      wsRef.current?.close();
      setIsListening(false);
      setLiveTranscript('');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ws = new WebSocket('ws://localhost:8001/api/voice/stream');
      wsRef.current = ws;

      ws.onopen = () => {
        setIsListening(true);
        const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        mediaRecorderRef.current = recorder;
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(e.data);
        };
        recorder.start(250);
      };

      let finalSentence = '';
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'interim') {
          setLiveTranscript(finalSentence + ' ' + data.text);
        } else if (data.type === 'final') {
          finalSentence += ' ' + data.text;
          setLiveTranscript(finalSentence);
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = setTimeout(() => {
            const trimmed = finalSentence.trim();
            if (trimmed) {
              handleSend(trimmed);
              finalSentence = '';
              setLiveTranscript('');
            }
          }, 1000);
        }
      };

      ws.onerror = () => setIsListening(false);
      ws.onclose = () => setIsListening(false);
    } catch {
      alert('Microphone access is required for Voice Mode.');
    }
  };

  // ── TTS helper — only speaks in voice mode ─────────────────────────────────
  const speakAgentMessage = (text: string) => {
    if (!isVoiceMode) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(v =>
      v.name.includes('Google UK English Female') ||
      v.name.includes('Samantha') ||
      v.name.includes('Natural'),
    );
    if (naturalVoice) utterance.voice = naturalVoice;
    utterance.rate  = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  // ── Razorpay popup ─────────────────────────────────────────────────────────
  const triggerRazorpay = (rzpOrd: any, keyId: string) => {
    const options = {
      key:         keyId,
      amount:      rzpOrd.amount,
      currency:    rzpOrd.currency,
      name:        'The Souled Stole',
      description: 'Conversational Checkout',
      order_id:    rzpOrd.id,
      handler: async (response: any) => {
        try {
          const verify = await fetch('http://localhost:8001/api/payments/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              razorpay_order_id:   response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature:  response.razorpay_signature,
            }),
          }).then(r => r.json());
          if (verify.status === 'payment_confirmed') {
            setMessages(prev => [...prev, { role: 'success', text: `✅ Payment verified!\nOrder ID: ${response.razorpay_order_id}` }]);
            setLiveCart([]);
            setRzpOrder(null);
          } else {
            setMessages(prev => [...prev, { role: 'system', text: `Verification failed: ${verify.detail}` }]);
          }
        } catch (e: any) {
          setMessages(prev => [...prev, { role: 'system', text: `Verification error: ${e.message}` }]);
        }
      },
      prefill: { name: 'Voice Shopper' },
      modal: {
        ondismiss: () => setMessages(prev => [...prev, { role: 'system', text: 'Payment window closed.' }]),
      },
      theme: { color: '#DC2626' },
    };
    // @ts-ignore
    const rzp = new (window as any).Razorpay(options);
    rzp.on('payment.failed', (response: any) => {
      setMessages(prev => [...prev, { role: 'system', text: `[PAYMENT FAILED] ${response.error.description}` }]);
    });
    rzp.open();
  };

  // ── Send message ────────────────────────────────────────────────────────────
  const handleSend = async (textToSend = input) => {
    const trimmed = textToSend.trim();
    if (!trimmed || loading) return;
    setInput('');

    // Read live values from refs — guaranteed current even inside a stale closure
    const currentCart    = liveCartRef.current;
    const currentHistory = historyRef.current;

    const newHistory = currentHistory
      ? `${currentHistory}\nUSER: ${trimmed}`
      : `USER: ${trimmed}`;

    setMessages(prev => [...prev, { role: 'user', text: trimmed }]);
    setLoading(true);

    try {
      const res = await sendChatMessage(
        trimmed,
        newHistory,
        currentCart.map(c => ({ sku: c.sku, qty: c.qty })),
      );

      // Update live cart — merge by SKU so re-adds increment qty instead of duplicating
      if (res.added_items?.length) {
        setLiveCart(prev => {
          const next = prev.map(item => ({ ...item })); // immutable copy
          for (const incoming of res.added_items as any[]) {
            const existing = next.find(c => c.sku === incoming.sku);
            const safeQty = Number(incoming.qty) || 1;
            if (existing) {
              existing.qty += safeQty;
            } else {
              next.push({
                sku:   incoming.sku,
                name:  incoming.name  ?? incoming.sku,
                price: Number(incoming.price) || 0,
                qty:   safeQty,
              });
            }
          }
          return next;
        });
      }

      // Absolute quantity overrides and removals (qty === 0 removes the item)
      if ((res as any).updated_items?.length) {
        setLiveCart(prev => {
          let next = prev.map(item => ({ ...item }));
          for (const update of (res as any).updated_items as any[]) {
            const idx = next.findIndex(c => c.sku === update.sku);
            if (idx < 0) continue;
            const newQty = Number(update.qty);
            if (newQty <= 0) {
              next.splice(idx, 1);   // remove entirely
            } else {
              next[idx].qty = newQty; // absolute override
            }
          }
          return next;
        });
      }

      if (res.audit_trail) setAuditLogs(prev => [...prev, res.audit_trail]);

      const agentReply = res.agent_message ?? 'Done.';

      if (res.action === 'ESCALATE') {
        setMessages(prev => [...prev, { role: 'agent', text: agentReply }]);
      } else if (res.action === 'AWAITING_CONFIRMATION') {
        setMessages(prev => [...prev, { role: 'confirm', text: agentReply, confirm: res }]);
      } else if (res.action === 'REJECT') {
        setMessages(prev => [...prev, { role: 'system', text: `[REJECTED] ${res.audit_trail?.action_taken}` }]);
      } else {
        setMessages(prev => [...prev, { role: 'agent', text: agentReply }]);
      }

      speakAgentMessage(agentReply);

      // Checkout — shut down mic, save order, auto-open Razorpay after TTS finishes
      if (res.is_checkout && res.razorpay_order) {
        if (isListening) {
          mediaRecorderRef.current?.stop();
          wsRef.current?.close();
          setIsListening(false);
          setLiveTranscript('');
        }
        setIsVoiceMode(false);
        const orderWithKey = { ...res.razorpay_order, key_id: res.razorpay_key_id };
        setRzpOrder(orderWithKey);
        // Delay so TTS finishes speaking before the modal pops up
        setTimeout(() => triggerRazorpay(res.razorpay_order, res.razorpay_key_id ?? ''), 1500);
      }

      setHistory(`${newHistory}\nAGENT: ${agentReply}`);
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'agent', text: `Error: ${e.message}` }]);
    }
    setLoading(false);
  };

  // ── Confirm purchase ────────────────────────────────────────────────────────
  const handleConfirm = async (res: ChatResponse) => {
    setLoading(true);
    try {
      const result = await confirmPurchase(res.cart.cart_id);
      if (result.action === 'EXECUTED' && result.razorpay_order?.id && !result.razorpay_order?.error) {
        setMessages(prev => prev.map(m =>
          m.confirm?.cart.cart_id === res.cart.cart_id
            ? { ...m, confirm: undefined, role: 'agent', text: 'Opening secure payment. Use UPI ID failure@razorpay to test the failure recovery flow.' }
            : m,
        ));
        if (result.audit_trail) setAuditLogs(prev => [...prev, result.audit_trail]);
        setLoading(false);
        setIsVoiceMode(false);

        const options = {
          key:         result.razorpay_key_id,
          amount:      result.razorpay_order.amount,
          currency:    result.razorpay_order.currency,
          name:        'The Souled Stole',
          description: `Order ${result.cart?.cart_id}`,
          order_id:    result.razorpay_order.id,
          handler: async (response: any) => {
            try {
              const verify = await fetch('http://localhost:8001/api/payments/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  razorpay_order_id:    response.razorpay_order_id,
                  razorpay_payment_id:  response.razorpay_payment_id,
                  razorpay_signature:   response.razorpay_signature,
                }),
              }).then(r => r.json());
              if (verify.status === 'payment_confirmed') {
                setMessages(prev => [...prev, { role: 'success', text: `✅ Payment verified!\nOrder ID: ${response.razorpay_order_id}` }]);
                setLiveCart([]);
              } else {
                setMessages(prev => [...prev, { role: 'system', text: `Verification failed: ${verify.detail}` }]);
              }
            } catch (e: any) {
              setMessages(prev => [...prev, { role: 'system', text: `Verification error: ${e.message}` }]);
            }
          },
          modal: {
            ondismiss: () => setMessages(prev => [...prev, { role: 'system', text: 'Payment window closed.' }]),
          },
          prefill: { name: 'TrustRail Demo' },
          theme:   { color: '#DC2626' },
        };

        const rzp = new (window as any).Razorpay(options);
        rzp.on('payment.failed', async (response: any) => {
          const error = response.error;
          try {
            const recovery = await fetch('http://localhost:8001/api/storefront/payment-failed', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                razorpay_payment_id: error.metadata?.payment_id || '',
                razorpay_order_id:   error.metadata?.order_id   || result.razorpay_order.id,
                error_code:          error.code,
                error_description:   error.description,
                error_reason:        error.reason,
              }),
            }).then(r => r.json());
            setMessages(prev => [...prev,
              { role: 'system', text: `[PAYMENT FAILED] ${error.description}` },
              { role: 'agent',  text: recovery.agent_message },
            ]);
          } catch {
            setMessages(prev => [...prev, { role: 'system', text: `Payment failed: ${error.description}` }]);
          }
        });
        rzp.open();
        return;
      }
      // Confirm failed path
      setMessages(prev => prev.map(m =>
        m.confirm?.cart.cart_id === res.cart.cart_id
          ? { ...m, confirm: undefined, role: 'system', text: `Order failed: ${result.error ?? JSON.stringify(result.razorpay_order)}` }
          : m,
      ));
    } catch (e: any) {
      setMessages(prev => [...prev, { role: 'system', text: `Confirm error: ${e.message}` }]);
    }
    setLoading(false);
  };

  const handleDeny = (cartId: string) =>
    setMessages(prev => prev.map(m =>
      m.confirm?.cart.cart_id === cartId
        ? { ...m, confirm: undefined, role: 'system', text: 'Purchase cancelled.' }
        : m,
    ));

  const handleFailure = async (reason: string) => {
    setMessages(prev => [...prev, { role: 'system', text: `[SYSTEM] Payment Failed: ${reason}` }]);
    setLoading(true);
    const recovery = await recoverPayment(reason);
    setMessages(prev => [...prev, { role: 'agent', text: recovery.agent_message }]);
    setLoading(false);
  };

  const cartTotal = liveCart.reduce((s, i) => s + i.price * i.qty, 0);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50 pb-20 font-sans">
      <Navbar cartCount={liveCart.length} onCartClick={() => setIsCartModalOpen(true)} />

      {/* ── Centered Live Cart Modal (z-40, voice widget stays on top at z-50) ── */}
      {isCartModalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden border border-gray-200">
            <div className="bg-slate-900 text-white px-5 py-4 flex justify-between items-center">
              <div className="flex items-center gap-2 font-bold text-lg">
                <ShoppingBag className="w-5 h-5" /> Live Cart
              </div>
              <X className="w-6 h-6 cursor-pointer hover:text-red-400 transition-colors" onClick={() => setIsCartModalOpen(false)} />
            </div>
            <div className="p-6 space-y-4 max-h-[50vh] overflow-y-auto">
              {liveCart.length === 0 ? (
                <p className="text-gray-400 text-center italic py-10">Your cart is empty. Ask the AI to add items!</p>
              ) : (
                liveCart.map((item, i) => (
                  <div key={i} className="flex justify-between items-center border-b border-gray-100 pb-4">
                    <div>
                      <p className="font-bold text-gray-800">{item.name}</p>
                      <p className="text-xs text-gray-500 font-mono mt-1">SKU: {item.sku} · Qty: {item.qty}</p>
                    </div>
                    <p className="font-bold text-lg font-mono">₹{(item.price * item.qty).toLocaleString()}</p>
                  </div>
                ))
              )}
            </div>
            <div className="bg-gray-50 px-6 py-4 border-t border-gray-200 flex justify-between items-center">
              <span className="text-lg font-black text-gray-800">Total</span>
              <span className="text-2xl font-black font-mono text-red-600">₹{cartTotal.toFixed(2)}</span>
            </div>
          </div>
        </div>
      )}

      {/* App header */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white px-6 py-4 flex justify-between items-center shadow-md">
        <div>
          <h1 className="font-bold text-lg tracking-tight">The Souled Stole</h1>
          <p className="text-xs text-slate-400 font-mono">Merchant Catalog &amp; Configuration</p>
        </div>
        <div className="flex bg-slate-800/80 p-1 rounded-xl border border-slate-700 gap-1">
          <button
            onClick={() => setActiveTab('store')}
            className={`px-5 py-2 text-xs font-bold rounded-lg transition-all ${activeTab === 'store' ? 'bg-cyan-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}
          >Catalog</button>
          <button
            onClick={() => setActiveTab('merchant')}
            className={`px-5 py-2 text-xs font-bold rounded-lg transition-all ${activeTab === 'merchant' ? 'bg-cyan-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}
          >Configuration</button>
        </div>
      </div>

      {activeTab === 'store' ? <ProductGrid catalog={catalog} /> : <MerchantConfigPanel />}

      {/* ── Live Audit Trail (bottom-left) ─────────────────────────────────── */}
      <div className="fixed bottom-6 left-6 z-50">
        {!auditOpen ? (
          <button
            onClick={() => setAuditOpen(true)}
            className="relative bg-slate-900 text-white p-4 rounded-full shadow-xl hover:bg-slate-800 transition-transform active:scale-95"
          >
            <Activity className="w-6 h-6" />
            {auditLogs.length > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center">
                {auditLogs.length}
              </span>
            )}
          </button>
        ) : (
          <div className="bg-white rounded-2xl shadow-2xl w-[420px] max-h-[600px] flex flex-col border border-gray-200 overflow-hidden">
            <div className="bg-slate-900 text-white px-5 py-4 flex justify-between items-center flex-shrink-0">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-red-400" />
                <span className="font-bold tracking-wide">Live Audit Trail</span>
                <span className="bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">{auditLogs.length}</span>
              </div>
              <X className="w-5 h-5 cursor-pointer hover:text-gray-300" onClick={() => setAuditOpen(false)} />
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
              {auditLogs.length === 0 ? (
                <p className="text-sm text-gray-400 italic text-center py-8">Awaiting AI decisions...</p>
              ) : (
                auditLogs.map((log, i) => (
                  <div key={i} className="bg-white rounded-lg border border-gray-200 p-3 shadow-sm">
                    <p className={`text-sm font-black font-mono mb-1 ${
                      log.action_taken?.includes('EXECUTE') || log.action_taken?.includes('PASS') ? 'text-green-600'
                      : log.action_taken?.includes('REJECT') ? 'text-red-700'
                      : 'text-orange-500'
                    }`}>{log.action_taken}</p>
                    {log.rule     && <p className="text-xs font-mono text-gray-500 break-all">{log.rule}</p>}
                    {log.evaluated && <p className="text-xs font-mono text-gray-400 mt-1">{log.evaluated}</p>}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Floating AI Concierge (bottom-right) ────────────────────────────── */}
      <div className="fixed bottom-6 right-6 z-50">
        {!isOpen ? (
          <button
            onClick={() => setIsOpen(true)}
            className="bg-red-600 text-white p-4 rounded-full shadow-2xl hover:bg-red-700 transition-transform active:scale-95"
          >
            <MessageSquare className="w-7 h-7" />
          </button>
        ) : (
          <div className="bg-white rounded-[2rem] shadow-[0_10px_40px_-10px_rgba(0,0,0,0.35)] w-[400px] h-[650px] flex flex-col border border-gray-200 overflow-hidden">

            {/* Header */}
            <div className="bg-slate-900 text-white px-5 py-4 flex justify-between items-center flex-shrink-0 rounded-t-[2rem]">
              <div className="flex items-center gap-3">
                <Bot className="w-6 h-6 text-red-400" />
                <div>
                  <p className="font-bold tracking-wide leading-none">Style Concierge</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">AI-powered shopping assistant</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsVoiceMode(v => !v)}
                  className={`px-3 py-1.5 text-[10px] uppercase tracking-wider font-bold rounded-full transition-colors ${
                    isVoiceMode ? 'bg-red-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {isVoiceMode ? 'Voice' : 'Text'}
                </button>
                <X
                  className="w-5 h-5 cursor-pointer text-slate-400 hover:text-white transition-colors"
                  onClick={() => setIsOpen(false)}
                />
              </div>
            </div>

            {/* ── Voice Mode ── */}
            {isVoiceMode ? (
              <div className="flex-1 flex flex-col bg-slate-900 overflow-hidden">
                {/* Pulsing orb */}
                <div className="flex-1 flex flex-col items-center justify-center relative">
                  <div className="absolute inset-0 bg-gradient-to-b from-slate-900 to-black pointer-events-none" />
                  <div className="relative flex items-center justify-center w-36 h-36 mb-10 z-10">
                    <div className={`absolute w-full h-full rounded-full bg-red-500/15 transition-all duration-500 ${isListening ? 'scale-[1.6] animate-pulse' : 'scale-100'}`} />
                    <div className={`absolute w-[78%] h-[78%] rounded-full bg-red-500/30 transition-all duration-300 ${isListening ? 'scale-[1.3]' : 'scale-100'}`} />
                    <button
                      onClick={toggleVoice}
                      className={`relative z-10 w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg ${
                        isListening
                          ? 'bg-red-600 shadow-[0_0_30px_rgba(220,38,38,0.5)]'
                          : 'bg-slate-800 border-2 border-slate-700 hover:border-slate-500'
                      }`}
                    >
                      {loading
                        ? <Headphones className="w-8 h-8 text-white animate-pulse" />
                        : <Mic className={`w-8 h-8 ${isListening ? 'text-white' : 'text-slate-400'}`} />
                      }
                    </button>
                  </div>

                  {/* Transcript / status */}
                  <div className="z-10 px-8 text-center min-h-[5rem]">
                    {loading ? (
                      <p className="text-red-400 font-mono text-sm animate-pulse">Agent is thinking...</p>
                    ) : (
                      <p className={`transition-all duration-300 leading-snug ${
                        liveTranscript
                          ? 'text-white text-base font-medium'
                          : 'text-slate-500 text-sm'
                      }`}>
                        {liveTranscript || (isListening ? 'Listening...' : 'Tap the mic to start.')}
                      </p>
                    )}
                  </div>
                </div>

                {/* Last agent reply in voice mode */}
                {messages.length > 1 && (
                  <div className="px-5 pb-5 flex-none">
                    {(() => {
                      const last = [...messages].reverse().find(m => m.role === 'agent');
                      return last ? (
                        <div className="bg-slate-800 rounded-2xl px-4 py-3 text-sm text-slate-200 leading-relaxed border border-slate-700">
                          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Last reply</p>
                          {last.text}
                        </div>
                      ) : null;
                    })()}
                  </div>
                )}

                {/* Live cart strip */}
                {liveCart.length > 0 && (
                  <div className="px-5 pb-4 flex-none border-t border-slate-800 pt-3">
                    <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">
                      Cart · ₹{cartTotal.toLocaleString()}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {liveCart.map((item, i) => (
                        <span key={i} className="text-xs bg-slate-800 text-slate-300 border border-slate-700 rounded-full px-3 py-1 font-mono">
                          {item.name} ×{item.qty}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* ── Text / Chat Mode ── */
              <>
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/50">
                  {messages.map((m, i) => {
                    // Confirmation card
                    if (m.role === 'confirm' && m.confirm) {
                      const cart = m.confirm.cart;
                      return (
                        <div key={i} className="flex flex-col gap-2">
                          <div className="flex gap-2 justify-start">
                            <div className="w-7 h-7 rounded-full bg-red-100 flex items-center justify-center text-red-600 flex-shrink-0 mt-1">
                              <Bot className="w-4 h-4" />
                            </div>
                            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-none p-4 text-sm text-gray-800 shadow-sm max-w-[85%] leading-relaxed">
                              {m.text}
                            </div>
                          </div>
                          <div className="ml-9 bg-white border-2 border-red-200 rounded-2xl p-4 shadow-sm max-w-[85%]">
                            <div className="flex items-center gap-1.5 mb-3">
                              <ShoppingBag className="w-4 h-4 text-red-600" />
                              <span className="text-xs font-bold text-red-700 uppercase tracking-wider">Confirm Purchase</span>
                            </div>
                            <div className="space-y-1.5 mb-4">
                              {cart.items.map((item, j) => (
                                <div key={j} className="flex justify-between text-sm text-gray-700">
                                  <span>{item.qty}× {item.sku}</span>
                                  <span className="font-mono">₹{(item.price * item.qty).toLocaleString()}</span>
                                </div>
                              ))}
                              {cart.discount_pct > 0 && (
                                <div className="flex justify-between text-sm text-green-600 font-bold">
                                  <span>Discount</span><span>-{cart.discount_pct}%</span>
                                </div>
                              )}
                              <div className="flex justify-between text-sm font-black text-gray-900 border-t border-gray-100 pt-2">
                                <span>Total</span>
                                <span className="font-mono">₹{cart.final_amount.toFixed(2)}</span>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleDeny(cart.cart_id)}
                                className="flex-1 flex items-center justify-center gap-1 py-2.5 rounded-xl border border-gray-300 text-gray-600 text-sm font-bold hover:bg-gray-50 transition-colors"
                              >
                                <XCircle className="w-4 h-4" /> Cancel
                              </button>
                              <button
                                onClick={() => handleConfirm(m.confirm!)}
                                className="flex-1 flex items-center justify-center gap-1 py-2.5 rounded-xl bg-red-600 text-white text-sm font-bold hover:bg-red-700 transition-colors shadow-md"
                              >
                                <CheckCircle className="w-4 h-4" /> Pay Now
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    }

                    // Success message
                    if (m.role === 'success') {
                      return (
                        <div key={i} className="flex gap-2">
                          <div className="w-7 h-7 rounded-full bg-green-100 flex items-center justify-center text-green-600 flex-shrink-0 mt-1">
                            <CheckCircle className="w-4 h-4" />
                          </div>
                          <div className="bg-green-50 border border-green-200 rounded-2xl rounded-bl-none p-4 text-sm font-mono text-green-800 shadow-sm max-w-[85%] whitespace-pre-wrap leading-relaxed">
                            {m.text}
                          </div>
                        </div>
                      );
                    }

                    // Standard message
                    return (
                      <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        {m.role === 'agent' && (
                          <div className="w-7 h-7 rounded-full bg-red-100 flex items-center justify-center text-red-600 flex-shrink-0 mt-1">
                            <Bot className="w-4 h-4" />
                          </div>
                        )}
                        <div className={`p-4 rounded-2xl max-w-[85%] text-sm leading-relaxed ${
                          m.role === 'user'   ? 'bg-slate-900 text-white rounded-br-none shadow-md'
                          : m.role === 'system' ? 'bg-red-50 text-red-800 border border-red-200 w-full text-xs font-mono'
                          : 'bg-white border border-gray-200 rounded-bl-none text-gray-800 shadow-sm'
                        }`}>
                          {m.text}
                        </div>
                      </div>
                    );
                  })}

                  {loading && (
                    <div className="flex items-center gap-2 text-gray-400 text-xs px-1">
                      <Activity className="w-4 h-4 animate-spin" />
                      Agent is processing...
                    </div>
                  )}

                  {/* Fallback Pay button — shown if Razorpay auto-popup was dismissed */}
                  {rzpOrder && (
                    <div className="bg-white border-2 border-emerald-400 rounded-xl p-4 shadow-sm max-w-[85%]">
                      <p className="font-semibold text-emerald-700 text-sm mb-1">Ready to checkout</p>
                      <p className="text-xs text-gray-500 mb-3">
                        Total: ₹{(rzpOrder.amount / 100).toFixed(2)}
                      </p>
                      <button
                        onClick={() => triggerRazorpay(rzpOrder, rzpOrder.key_id)}
                        className="w-full bg-black text-white text-sm font-semibold py-2.5 rounded-lg hover:bg-gray-800 transition-colors"
                      >
                        Pay via Razorpay
                      </button>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Text input */}
                <div className="flex-none p-4 bg-white border-t border-gray-100 flex gap-2 items-center">
                  <input
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSend()}
                    placeholder="Ask for recommendations..."
                    className="flex-1 bg-gray-100 border-none rounded-full px-5 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-200 transition-all"
                  />
                  <button
                    onClick={() => handleSend()}
                    disabled={loading}
                    className="bg-red-600 text-white p-3 rounded-full hover:bg-red-700 disabled:opacity-40 transition-transform active:scale-95 shadow-md"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
