import React, { useEffect, useState, useRef } from 'react';
import Navbar from './components/Navbar';
import ProductGrid from './components/ProductGrid';
import MerchantConfigPanel from './components/MerchantConfigPanel';
import { fetchCatalog, sendChatMessage, recoverPayment, confirmPurchase } from './api/client';
import {
  MessageSquare, Send, Bot, Activity, X,
  CheckCircle, XCircle, ShoppingBag, Mic, Headphones,
} from 'lucide-react';
import { ChatResponse, CartItem } from './types/api';

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
  const [liveCart, setLiveCart]         = useState<LiveCartItem[]>(() => {
    try {
      const saved = sessionStorage.getItem('b2c_liveCart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [history, setHistory]           = useState(() => {
    try {
      const saved = sessionStorage.getItem('b2c_history');
      return saved ? JSON.parse(saved) : '';
    } catch {
      return '';
    }
  });
  const [rzpOrder, setRzpOrder]         = useState<{ amount: number; currency: string; id: string; key_id: string } | null>(() => {
    try {
      const saved = sessionStorage.getItem('b2c_rzpOrder');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [activeCampaigns, setActiveCampaigns] = useState<any[]>(() => {
    try {
      const saved = sessionStorage.getItem('b2c_campaigns');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Refs to prevent stale closures inside the WebSocket voice loop.
  // The silence-timer callback captures state at mic-open time; these refs
  // always hold the current value regardless of when they're read.
  const liveCartRef  = useRef<LiveCartItem[]>([]);
  const historyRef   = useRef('');

  useEffect(() => { liveCartRef.current = liveCart; },  [liveCart]);
  useEffect(() => { historyRef.current  = history;  },  [history]);
  useEffect(() => {
    try { sessionStorage.setItem('b2c_liveCart', JSON.stringify(liveCart)); } catch {}
  }, [liveCart]);
  useEffect(() => {
    try { sessionStorage.setItem('b2c_history', JSON.stringify(history)); } catch {}
  }, [history]);
  useEffect(() => {
    try { sessionStorage.setItem('b2c_rzpOrder', JSON.stringify(rzpOrder)); } catch {}
  }, [rzpOrder]);
  useEffect(() => {
    try { sessionStorage.setItem('b2c_campaigns', JSON.stringify(activeCampaigns)); } catch {}
  }, [activeCampaigns]);

  // Voice / Deepgram state
  const [isListening, setIsListening]   = useState(false);
  const [liveTranscript, setLiveTranscript] = useState('');
  const wsRef                           = useRef<WebSocket | null>(null);
  const mediaRecorderRef                = useRef<MediaRecorder | null>(null);
  const silenceTimerRef                 = useRef<ReturnType<typeof setTimeout> | null>(null);

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

      if ((res as any).active_campaigns) {
        setActiveCampaigns((res as any).active_campaigns);
      }

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

  let subtotal = liveCart.reduce((s, i) => s + i.price * i.qty, 0);
  let discountAmount = 0;

  liveCart.forEach(item => {
    const catItem: any = (catalog as any[]).find(c => c.sku === item.sku);
    if (catItem) {
      // Visual inventory cap so the discount math can't exceed live stock
      const actualQty = Math.min(Number(item.qty), Number(catItem.in_stock));
      let bestDiscount = 0;

      activeCampaigns.forEach((camp: any) => {
        const targetSku = camp.target_sku || "NONE";
        const targetCat = camp.target_category || "all";
        const isEligible =
          (targetSku !== "NONE" && item.sku === targetSku) ||
          (targetSku === "NONE" && (targetCat === 'all' || targetCat === catItem.category));
        if (isEligible && Number(camp.discount_pct) > bestDiscount) {
          bestDiscount = Number(camp.discount_pct);
        }
      });

      discountAmount += (item.price * actualQty) * (bestDiscount / 100);
    }
  });

  const cartTotal = Math.max(0, subtotal - discountAmount);

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
            <div className="bg-white p-6 border-t border-gray-100 flex flex-col gap-2">
              {discountAmount > 0 && (
                <div className="flex justify-between items-center text-sm font-bold text-green-600">
                  <span>Campaign Discount (best {Math.max(0, ...activeCampaigns.map((c: any) => Number(c.discount_pct) || 0))}%)</span>
                  <span>-₹{discountAmount.toFixed(2)}</span>
                </div>
              )}
              <div className="flex justify-between items-center mt-2 pt-2 border-t border-gray-100">
                <span className="text-xl font-bold text-[#002155]">Total</span>
                <div className="text-right">
                  {discountAmount > 0 && <span className="text-sm line-through text-gray-400 mr-2">₹{subtotal.toFixed(2)}</span>}
                  <span className="text-2xl font-black text-[#305EFF]">₹{cartTotal.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* App header */}
      <div className="bg-[#EC2D37] border-b border-[#c5242d] text-white px-6 py-4 flex justify-between items-center shadow-md">
        <div>
          <h1 className="font-bold text-lg tracking-tight text-white">The Souled Stole</h1>
          <p className="text-xs text-white/80">Merchant Catalog &amp; Configuration</p>
        </div>
        <div className="relative flex items-center bg-[#b8242d] border border-white/20 rounded-full p-1 shadow-inner">
          <button
            onClick={() => setActiveTab('store')}
            aria-pressed={activeTab === 'store'}
            className={`relative z-10 px-5 py-2 text-xs font-bold rounded-full transition-all duration-200 ${
              activeTab === 'store'
                ? 'bg-white text-[#EC2D37] shadow-[0_2px_8px_-2px_rgba(0,0,0,0.25)]'
                : 'text-white/85 hover:text-white'
            }`}
          >Catalog</button>
          <button
            onClick={() => setActiveTab('merchant')}
            aria-pressed={activeTab === 'merchant'}
            className={`relative z-10 px-5 py-2 text-xs font-bold rounded-full transition-all duration-200 ${
              activeTab === 'merchant'
                ? 'bg-white text-[#EC2D37] shadow-[0_2px_8px_-2px_rgba(0,0,0,0.25)]'
                : 'text-white/85 hover:text-white'
            }`}
          >Configuration</button>
        </div>
      </div>

      {activeTab === 'store' ? <ProductGrid catalog={catalog} /> : <MerchantConfigPanel />}

      {/* ── Floating AI Concierge (catalog tab only) ────────────────────────── */}
      {activeTab === 'store' && (
      <div className="fixed bottom-6 right-6 z-50">
        {!isOpen ? (
          <button
            onClick={() => setIsOpen(true)}
            className="bg-[#305EFF] text-white p-4 rounded-full shadow-2xl hover:bg-[#002155] transition-transform active:scale-95"
          >
            <MessageSquare className="w-7 h-7" />
          </button>
        ) : (
          <div className="bg-[#002155] rounded-[2rem] shadow-[0_10px_60px_-10px_rgba(0,33,85,0.55),0_0_0_1px_rgba(0,33,85,0.6)] w-[400px] h-[650px] flex flex-col border border-[#001a3d] overflow-hidden">

            {/* Header */}
            <div className="bg-[#002155] text-white px-5 py-4 flex justify-between items-center flex-shrink-0 rounded-t-[2rem] border-b border-white/10 shadow-[0_4px_24px_-8px_rgba(48,94,255,0.5)]">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#305EFF] to-[#0096FF] flex items-center justify-center shadow-[0_0_18px_rgba(48,94,255,0.5)]">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="font-bold tracking-wide leading-none text-white">Razor</p>
                  <p className="text-[10px] text-[#A6D8FF] mt-0.5 font-medium">AI-powered shopping assistant</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {/* Razorpay-style segmented toggle. The active mode is filled with
                    #305EFF and shows its icon + label; the inactive mode is shown
                    as a discoverable ghost button so users see voice is available. */}
                <div className="relative flex items-center bg-[#F6F8FD] border border-gray-200 rounded-full p-1">
                  <button
                    onClick={() => setIsVoiceMode(false)}
                    aria-pressed={!isVoiceMode}
                    className={`relative z-10 flex items-center gap-1.5 px-3 py-1.5 text-[10px] uppercase tracking-wider font-bold rounded-full transition-all duration-200 ${
                      !isVoiceMode
                        ? 'bg-[#305EFF] text-white shadow-[0_2px_8px_-2px_rgba(48,94,255,0.5)]'
                        : 'text-gray-500 hover:text-[#002155]'
                    }`}
                  >
                    <Bot className="w-3.5 h-3.5" />
                    Text
                  </button>
                  <button
                    onClick={() => setIsVoiceMode(true)}
                    aria-pressed={isVoiceMode}
                    className={`relative z-10 flex items-center gap-1.5 px-3 py-1.5 text-[10px] uppercase tracking-wider font-bold rounded-full transition-all duration-200 ${
                      isVoiceMode
                        ? 'bg-[#305EFF] text-white shadow-[0_2px_8px_-2px_rgba(48,94,255,0.5)]'
                        : 'text-gray-500 hover:text-[#002155]'
                    }`}
                  >
                    <Mic className="w-3.5 h-3.5" />
                    Voice
                  </button>
                </div>
                <X
                  className="w-5 h-5 cursor-pointer text-gray-400 hover:text-[#002155] transition-colors"
                  onClick={() => setIsOpen(false)}
                />
              </div>
            </div>

            {/* ── Voice Mode ── */}
            {isVoiceMode ? (
              <div className="flex-1 flex flex-col bg-white overflow-hidden">
                {/* Pulsing orb */}
                <div className="flex-1 flex flex-col items-center justify-center relative">
                  <div className="relative flex items-center justify-center w-36 h-36 mb-10 z-10">
                    <div className={`absolute w-full h-full rounded-full bg-[#305EFF]/15 transition-all duration-500 ${isListening ? 'scale-[1.6] animate-pulse' : 'scale-100'}`} />
                    <div className={`absolute w-[78%] h-[78%] rounded-full bg-[#305EFF]/30 transition-all duration-300 ${isListening ? 'scale-[1.3]' : 'scale-100'}`} />
                    <button
                      onClick={toggleVoice}
                      className={`relative z-10 w-20 h-20 rounded-full flex items-center justify-center transition-all shadow-lg ${
                        isListening
                          ? 'bg-[#305EFF] shadow-[0_0_30px_rgba(48,94,255,0.5)]'
                          : 'bg-white border-2 border-[#305EFF]/30 hover:border-[#305EFF]'
                      }`}
                    >
                      {loading
                        ? <Headphones className="w-8 h-8 text-white animate-pulse" />
                        : <Mic className={`w-8 h-8 ${isListening ? 'text-white' : 'text-[#305EFF]'}`} />
                      }
                    </button>
                  </div>

                  {/* Transcript / status */}
                  <div className="z-10 px-8 text-center min-h-[5rem]">
                    {loading ? (
                      <p className="text-[#305EFF] font-mono text-sm animate-pulse">Agent is thinking...</p>
                    ) : (
                      <p className={`transition-all duration-300 leading-snug ${
                        liveTranscript
                          ? 'text-[#002155] text-base font-medium'
                          : 'text-gray-500 text-sm'
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
                        <div className="bg-[#F6F8FD] rounded-2xl px-4 py-3 text-sm text-[#002155] leading-relaxed border border-[#305EFF]/20 shadow-sm">
                          <p className="text-[10px] text-[#305EFF] uppercase tracking-wider mb-1">Last reply</p>
                          {last.text}
                        </div>
                      ) : null;
                    })()}
                  </div>
                )}

                {/* Live cart strip */}
                {liveCart.length > 0 && (
                  <div className="px-5 pb-4 flex-none border-t border-gray-200 pt-3 bg-white">
                    <p className="text-[10px] text-[#305EFF] uppercase tracking-wider mb-2">
                      Cart · ₹{cartTotal.toLocaleString()}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {liveCart.map((item, i) => (
                        <span key={i} className="text-xs bg-[#F6F8FD] text-[#002155] border border-[#305EFF]/20 rounded-full px-3 py-1 font-mono">
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
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white">
                  {messages.map((m, i) => {
                    // Confirmation card
                    if (m.role === 'confirm' && m.confirm) {
                      const cart = m.confirm.cart;
                      return (
                        <div key={i} className="flex flex-col gap-2">
                          <div className="flex gap-2 justify-start">
                            <div className="w-7 h-7 rounded-full bg-[#305EFF]/10 flex items-center justify-center text-[#305EFF] flex-shrink-0 mt-1">
                              <Bot className="w-4 h-4" />
                            </div>
                            <div className="bg-white border border-[#305EFF]/20 rounded-2xl rounded-bl-none p-4 text-sm text-[#002155] shadow-sm max-w-[85%] leading-relaxed">
                              {m.text}
                            </div>
                          </div>
                          <div className="ml-9 bg-white border-2 border-[#305EFF]/30 rounded-2xl p-4 shadow-md max-w-[85%]">
                            <div className="flex items-center gap-1.5 mb-3">
                              <ShoppingBag className="w-4 h-4 text-[#305EFF]" />
                              <span className="text-xs font-bold text-[#002155] uppercase tracking-wider">Confirm Purchase</span>
                            </div>
                            <div className="space-y-1.5 mb-4">
                              {cart.items.map((item, j) => (
                                <div key={j} className="flex justify-between text-sm text-gray-700">
                                  <span>{item.qty}× {item.sku}</span>
                                  <span className="font-mono">₹{(item.price * item.qty).toLocaleString()}</span>
                                </div>
                              ))}
                              {cart.discount_pct > 0 && (
                                <div className="flex justify-between text-sm text-[#0096FF] font-bold">
                                  <span>Discount</span><span>-{cart.discount_pct}%</span>
                                </div>
                              )}
                              <div className="flex justify-between text-sm font-black text-[#002155] border-t border-gray-200 pt-2">
                                <span>Total</span>
                                <span className="font-mono">₹{cart.final_amount.toFixed(2)}</span>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleDeny(cart.cart_id)}
                                className="flex-1 flex items-center justify-center gap-1 py-2.5 rounded-xl border border-gray-300 text-gray-500 text-sm font-bold hover:bg-gray-50 transition-colors"
                              >
                                <XCircle className="w-4 h-4" /> Cancel
                              </button>
                              <button
                                onClick={() => handleConfirm(m.confirm!)}
                                className="flex-1 flex items-center justify-center gap-1 py-2.5 rounded-xl bg-[#305EFF] text-white text-sm font-bold hover:bg-[#002155] transition-colors shadow-md"
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
                          <div className="w-7 h-7 rounded-full bg-[#0096FF]/10 flex items-center justify-center text-[#0096FF] flex-shrink-0 mt-1">
                            <CheckCircle className="w-4 h-4" />
                          </div>
                          <div className="bg-[#F6F8FD] border border-[#305EFF]/30 rounded-2xl rounded-bl-none p-4 text-sm font-mono text-[#002155] shadow-sm max-w-[85%] whitespace-pre-wrap leading-relaxed">
                            {m.text}
                          </div>
                        </div>
                      );
                    }

                    // Standard message
                    return (
                      <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        {m.role === 'agent' && (
                          <div className="w-7 h-7 rounded-full bg-[#305EFF]/10 flex items-center justify-center text-[#305EFF] flex-shrink-0 mt-1">
                            <Bot className="w-4 h-4" />
                          </div>
                        )}
                        <div className={`p-4 rounded-2xl max-w-[85%] text-sm leading-relaxed ${
                          m.role === 'user'   ? 'bg-[#305EFF] text-white rounded-br-none shadow-md'
                          : m.role === 'system' ? 'bg-red-50 text-red-800 border border-red-200 w-full text-xs font-mono'
                          : 'bg-white border border-gray-100 rounded-bl-none text-[#002155] shadow-sm'
                        }`}>
                          {m.text}
                        </div>
                      </div>
                    );
                  })}

                  {loading && (
                    <div className="flex items-center gap-2 text-[#305EFF] text-xs px-1">
                      <Activity className="w-4 h-4 animate-spin" />
                      Agent is processing...
                    </div>
                  )}

                  {/* Fallback Pay button — shown if Razorpay auto-popup was dismissed */}
                  {rzpOrder && (
                    <div className="bg-white border-2 border-[#305EFF]/40 rounded-xl p-4 shadow-md max-w-[85%]">
                      <p className="font-semibold text-[#002155] text-sm mb-1">Ready to checkout</p>
                      <p className="text-xs text-gray-500 mb-3">
                        Total: ₹{(rzpOrder.amount / 100).toFixed(2)}
                      </p>
                      <button
                        onClick={() => triggerRazorpay(rzpOrder, rzpOrder.key_id)}
                        className="w-full bg-[#305EFF] text-white text-sm font-semibold py-2.5 rounded-lg hover:bg-[#002155] transition-colors"
                      >
                        Pay via Razorpay
                      </button>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Text input */}
                <div className="flex-none p-3 bg-white border-t border-gray-200 flex gap-2 items-center">
                  <input
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSend()}
                    placeholder="Ask for recommendations..."
                    className="flex-1 bg-[#F6F8FD] border border-gray-200 rounded-full px-5 py-3 text-sm focus:outline-none focus:border-[#305EFF] focus:ring-2 focus:ring-[#305EFF]/20 transition-all text-[#002155]"
                  />
                  <button
                    onClick={() => handleSend()}
                    disabled={loading}
                    className="bg-[#305EFF] text-white p-3 rounded-full hover:bg-[#002155] disabled:opacity-40 transition-transform active:scale-95 shadow-md"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
      )}
    </div>
  );
}
