import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Mic, Send, Bot, ShoppingBag, CreditCard, X, Loader2 } from 'lucide-react';

interface CartItem {
  sku: string;
  name: string;
  price: number;
  qty: number;
}

interface Message {
  role: 'user' | 'agent';
  content: string;
}

declare const window: Window & {
  SpeechRecognition?: any;
  webkitSpeechRecognition?: any;
  Razorpay?: any;
};

export default function B2CStorefront() {
  const [input,       setInput]       = useState('');
  const [isListening, setIsListening] = useState(false);
  const [messages,    setMessages]    = useState<Message[]>([
    { role: 'agent', content: "Hey! I'm your Style Concierge. What are you looking for today?" },
  ]);
  const [cart,    setCart]    = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [order,   setOrder]   = useState<{ amount: number; id: string; currency: string } | null>(null);
  const [rzpKey,  setRzpKey]  = useState('');

  const chatEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // ── Voice input ────────────────────────────────────────────────────────────
  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('Voice input is not supported in this browser.'); return; }

    const recognition = new SR();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart  = () => setIsListening(true);
    recognition.onend    = () => setIsListening(false);
    recognition.onerror  = () => setIsListening(false);
    recognition.onresult = (event: any) => {
      const transcript: string = event.results[0][0].transcript;
      setInput(transcript);
      sendMessage(transcript);
    };
    recognition.start();
  };

  // ── Chat send ───────────────────────────────────────────────────────────────
  const sendMessage = async (text = input) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    setInput('');

    const userMsg: Message = { role: 'user', content: trimmed };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setLoading(true);

    try {
      const historyStr = updatedMessages
        .map(m => `${m.role.toUpperCase()}: ${m.content}`)
        .join('\n');

      const res = await axios.post('http://localhost:8001/api/storefront/chat', {
        user_message: trimmed,
        history: historyStr,
        current_cart: cart.map(c => ({ sku: c.sku, qty: c.qty })),
      });

      const data = res.data;

      setMessages(prev => [...prev, { role: 'agent', content: data.agent_message }]);

      if (data.added_items?.length > 0) {
        setCart(prev => {
          const next = [...prev];
          for (const incoming of data.added_items as CartItem[]) {
            const existing = next.find(c => c.sku === incoming.sku);
            if (existing) {
              existing.qty += incoming.qty;
            } else {
              next.push(incoming);
            }
          }
          return next;
        });
      }

      if (data.razorpay_order) {
        setOrder(data.razorpay_order);
        setRzpKey(data.razorpay_key_id ?? '');
      }
    } catch {
      setMessages(prev => [...prev, { role: 'agent', content: 'Connection error — please try again.' }]);
    }

    setLoading(false);
  };

  // ── Razorpay checkout ───────────────────────────────────────────────────────
  const openCheckout = () => {
    if (!order || !window.Razorpay) return;
    const rzp = new window.Razorpay({
      key:      rzpKey,
      amount:   order.amount,
      currency: order.currency,
      name:     'The Souled Stole',
      order_id: order.id,
      handler: (response: any) => {
        setMessages(prev => [
          ...prev,
          {
            role: 'agent',
            content: `Payment successful! Payment ID: ${response.razorpay_payment_id}`,
          },
        ]);
        setOrder(null);
        setCart([]);
      },
      modal: {
        ondismiss: () =>
          setMessages(prev => [...prev, { role: 'agent', content: 'Payment window closed.' }]),
      },
      theme: { color: '#000000' },
    });
    rzp.open();
  };

  const removeItem = (sku: string) =>
    setCart(prev => prev.filter(c => c.sku !== sku));

  const cartTotal = cart.reduce((sum, item) => sum + item.price * item.qty, 0);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-[calc(100vh-8rem)] max-w-5xl mx-auto mt-6 border border-gray-200 rounded-2xl shadow-xl overflow-hidden bg-white">

      {/* ── Chat panel ─────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Header */}
        <div className="bg-black text-white px-5 py-4 flex items-center gap-3 flex-none">
          <Bot className="w-5 h-5 text-gray-300" />
          <div>
            <p className="font-semibold text-sm">AI Style Concierge</p>
            <p className="text-[11px] text-gray-400">Powered by Minimax · OpenRouter</p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4 bg-gray-50">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'agent' && (
                <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center text-white mr-2 mt-1 flex-none">
                  <Bot className="w-4 h-4" />
                </div>
              )}
              <div className={`max-w-[78%] px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
                m.role === 'user'
                  ? 'bg-black text-white rounded-br-none'
                  : 'bg-white border border-gray-200 text-gray-800 rounded-bl-none'
              }`}>
                {m.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center flex-none">
                <Loader2 className="w-4 h-4 text-white animate-spin" />
              </div>
              <span>Thinking...</span>
            </div>
          )}

          {/* Checkout card */}
          {order && (
            <div className="bg-white border-2 border-emerald-400 rounded-xl p-4 max-w-[78%] shadow-sm">
              <p className="font-semibold text-emerald-700 flex items-center gap-2 mb-1">
                <CreditCard className="w-4 h-4" /> Ready to checkout
              </p>
              <p className="text-sm text-gray-600 mb-3">
                Total: ₹{(order.amount / 100).toFixed(2)}
              </p>
              <button
                onClick={openCheckout}
                className="w-full bg-black text-white text-sm font-semibold py-2.5 rounded-lg hover:bg-gray-800 transition-colors"
              >
                Pay Now
              </button>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input bar */}
        <div className="flex-none px-4 py-3 bg-white border-t border-gray-200 flex gap-2 items-center">
          <button
            onClick={startListening}
            className={`p-3 rounded-full transition-colors ${
              isListening
                ? 'bg-red-500 text-white animate-pulse'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            title="Voice input"
          >
            <Mic className="w-5 h-5" />
          </button>
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder={isListening ? 'Listening...' : 'Ask for something...'}
            className="flex-1 border border-gray-200 rounded-full px-4 py-2.5 text-sm focus:outline-none focus:border-gray-400 bg-gray-50"
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading}
            className="bg-black text-white p-3 rounded-full hover:bg-gray-800 disabled:opacity-40 transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* ── Live cart sidecar ───────────────────────────────────────────────── */}
      <div className="w-64 flex flex-col border-l border-gray-200 flex-none">

        <div className="px-4 py-3.5 border-b border-gray-100 flex items-center justify-between bg-gray-50 flex-none">
          <div className="flex items-center gap-2 font-semibold text-sm text-gray-800">
            <ShoppingBag className="w-4 h-4" /> Live Cart
          </div>
          <span className="bg-black text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
            {cart.length}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
          {cart.length === 0 ? (
            <p className="text-xs text-gray-400 text-center mt-8 leading-relaxed px-2">
              Your cart is empty. Tell the concierge what you'd like.
            </p>
          ) : (
            cart.map((item, i) => (
              <div key={i} className="bg-white border border-gray-100 rounded-xl p-3 group relative shadow-sm">
                <button
                  onClick={() => removeItem(item.sku)}
                  className="absolute top-2 right-2 text-gray-300 hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
                <p className="text-xs font-semibold text-gray-800 leading-snug pr-4">{item.name}</p>
                <div className="flex justify-between items-center mt-1.5 text-[11px] font-mono text-gray-400">
                  <span>{item.sku} × {item.qty}</span>
                  <span className="font-semibold text-gray-700">₹{(item.price * item.qty).toLocaleString()}</span>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="flex-none p-4 bg-gray-50 border-t border-gray-200">
          <div className="flex justify-between items-baseline mb-0.5">
            <span className="text-sm font-semibold text-gray-700">Total</span>
            <span className="text-base font-bold text-gray-900 font-mono">₹{cartTotal.toLocaleString()}</span>
          </div>
          <p className="text-[10px] text-gray-400 text-right">Incl. all taxes</p>
          {cart.length > 0 && !order && (
            <button
              onClick={() => sendMessage('I want to checkout')}
              disabled={loading}
              className="w-full mt-3 bg-black text-white text-xs font-semibold py-2.5 rounded-lg hover:bg-gray-800 disabled:opacity-40 transition-colors"
            >
              Checkout
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
