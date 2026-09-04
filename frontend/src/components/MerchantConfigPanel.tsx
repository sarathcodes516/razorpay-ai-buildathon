import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Sliders, Database, Check, Sparkles, Shield, Tag,
  TrendingUp, Package, ArrowUpRight,
} from 'lucide-react';

const API = 'http://localhost:8001';
const RZP_BLUE = '#305EFF';
const RZP_DEEP = '#002155';
const RZP_LIGHT = '#0096FF';

export default function MerchantConfigPanel() {
  const [config, setConfig] = useState<any>(null);
  const [maxDiscount, setMaxDiscount] = useState(15);
  const [highStockThreshold, setHighStockThreshold] = useState(20);
  const [saved, setSaved] = useState(false);
  const [stockEdits, setStockEdits] = useState<Record<string, number>>({});
  const [stockSaved, setStockSaved] = useState<Record<string, boolean>>({});
  const [campaignPrompt, setCampaignPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedCampaign, setGeneratedCampaign] = useState<any>(null);
  const [campaignSaved, setCampaignSaved] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/merchant/config`).then(res => {
      setConfig(res.data);
      setMaxDiscount(res.data.policy.max_allowable_discount_pct);
      setHighStockThreshold(res.data.policy.high_stock_threshold);
      const edits: Record<string, number> = {};
      res.data.catalog.forEach((item: any) => { edits[item.sku] = item.in_stock; });
      setStockEdits(edits);
    });
  }, []);

  const handleSavePolicy = async () => {
    await axios.post(`${API}/api/merchant/policy`, {
      max_allowable_discount_pct: Number(maxDiscount),
      high_stock_threshold: Number(highStockThreshold)
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleSaveStock = async (sku: string) => {
    await axios.post(`${API}/api/merchant/inventory`, {
      sku,
      in_stock: Number(stockEdits[sku])
    });
    setStockSaved(prev => ({ ...prev, [sku]: true }));
    setConfig((prev: any) => ({
      ...prev,
      catalog: prev.catalog.map((item: any) =>
        item.sku === sku ? { ...item, in_stock: Number(stockEdits[sku]) } : item
      )
    }));
    setTimeout(() => setStockSaved(prev => ({ ...prev, [sku]: false })), 2000);
  };

  const handleGenerateCampaign = async () => {
    if (!campaignPrompt.trim()) return;
    setIsGenerating(true);
    try {
      const res = await axios.post(`${API}/api/merchant/campaign/generate`, { prompt: campaignPrompt });
      setGeneratedCampaign(res.data);
    } catch (e) { console.error(e); }
    setIsGenerating(false);
  };

  const handleApplyCampaign = async () => {
    if (!generatedCampaign) return;
    await axios.post(`${API}/api/merchant/campaign/apply`, generatedCampaign);
    setConfig((prev: any) => ({
      ...prev,
      campaigns: [...(prev?.campaigns || []), generatedCampaign],
    }));
    setCampaignSaved(true);
    setTimeout(() => setCampaignSaved(false), 2000);
  };

  const handleDeleteCampaign = async (name: string) => {
    await axios.delete(`${API}/api/merchant/campaign/${encodeURIComponent(name)}`);
    setConfig((prev: any) => ({
      ...prev,
      campaigns: (prev?.campaigns || []).filter((c: any) => c.name !== name),
    }));
  };

  if (!config) return (
    <div className="max-w-4xl mx-auto p-8 text-sm text-gray-500">
      Loading dynamic merchant parameters...
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F6F8FD] px-6 py-8 space-y-6" style={{ maxWidth: '72rem', marginInline: 'auto' }}>
      {/* ── Page header (Razorpay-tinted glassmorphism) ─────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl p-7
                      bg-gradient-to-br from-[#002155]/85 via-[#003382]/80 to-[#305EFF]/80
                      backdrop-blur-2xl backdrop-saturate-150
                      border border-[#305EFF]/40
                      shadow-[0_18px_50px_-20px_rgba(0,33,85,0.6),inset_0_1px_0_rgba(255,255,255,0.18)]">
        {/* Brighter orbs to give the glass more depth */}
        <div className="absolute -right-16 -top-16 w-72 h-72 rounded-full bg-[#0096FF]/55 blur-3xl pointer-events-none" />
        <div className="absolute -left-10 -bottom-16 w-64 h-64 rounded-full bg-[#305EFF]/70 blur-3xl pointer-events-none" />
        <div className="absolute right-1/3 top-1/2 -translate-y-1/2 w-44 h-44 rounded-full bg-[#0096FF]/40 blur-2xl pointer-events-none" />

        <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-white/15 backdrop-blur-md border border-white/25 shadow-[0_4px_14px_-6px_rgba(0,150,255,0.55)]">
              <Sliders className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">Merchant Runtime Policy Engine</h2>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider
                                 bg-white/15 text-white border border-white/30">
                  Seller Side
                </span>
              </div>
              <p className="text-xs text-white/80 mt-1 max-w-md">
                Modify store rules live. The AI Merchant Agent reads this state on every negotiation turn — no restart needed.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="px-3 py-1.5 rounded-full bg-white/15 backdrop-blur-md border border-white/25
                            text-[11px] font-semibold text-white flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse" />
              Live · in sync with B2C
            </div>
            <div className="px-3 py-1.5 rounded-full bg-white/15 backdrop-blur-md border border-white/25
                            text-[11px] font-semibold text-white flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-[#9AD8FF]" /> Bounded &amp; Gated
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Policy Sliders */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-[0_4px_24px_-12px_rgba(0,33,85,0.10)] hover:shadow-[0_6px_28px_-12px_rgba(48,94,255,0.20)] transition-shadow overflow-hidden">
          <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 text-[#305EFF]">
              <Sliders className="w-3.5 h-3.5" /> Store Margin Rules
            </h3>
            <span className="text-[10px] font-bold text-[#002155] bg-[#F6F8FD] border border-[#305EFF]/15 rounded-full px-2.5 py-0.5">
              Risk Caps
            </span>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <div className="flex justify-between items-baseline mb-2">
                <label className="text-[11px] font-bold uppercase tracking-wider text-[#002155]">Max Allowable Discount</label>
                <span className="text-2xl font-black tabular-nums text-[#305EFF]">{maxDiscount}%</span>
              </div>
              <div className="relative">
                <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-[#F6F8FD] pointer-events-none" />
                <div
                  className="absolute top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-gradient-to-r from-[#305EFF] to-[#0096FF] pointer-events-none transition-all"
                  style={{ width: `${((maxDiscount - 5) / 35) * 100}%` }}
                />
                <input
                  type="range" min="5" max="40" step="5"
                  value={maxDiscount}
                  onChange={e => setMaxDiscount(Number(e.target.value))}
                  className="relative w-full cursor-pointer appearance-none bg-transparent [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-[#305EFF] [&::-webkit-slider-thumb]:shadow-[0_2px_6px_rgba(48,94,255,0.4)] [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-[#305EFF]"
                />
              </div>
              <div className="flex justify-between text-[10px] font-medium text-gray-400 mt-2">
                <span>5% · tight margins</span>
                <span>40% · clearance</span>
              </div>
            </div>

            <div>
              <div className="flex justify-between items-baseline mb-2">
                <label className="text-[11px] font-bold uppercase tracking-wider text-[#002155]">High Stock Threshold</label>
                <span className="text-2xl font-black tabular-nums text-[#305EFF]">{highStockThreshold}</span>
              </div>
              <div className="relative">
                <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-[#F6F8FD] pointer-events-none" />
                <div
                  className="absolute top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-gradient-to-r from-[#305EFF] to-[#0096FF] pointer-events-none transition-all"
                  style={{ width: `${((highStockThreshold - 5) / 45) * 100}%` }}
                />
                <input
                  type="range" min="5" max="50" step="5"
                  value={highStockThreshold}
                  onChange={e => setHighStockThreshold(Number(e.target.value))}
                  className="relative w-full cursor-pointer appearance-none bg-transparent [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-[#305EFF] [&::-webkit-slider-thumb]:shadow-[0_2px_6px_rgba(48,94,255,0.4)] [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-[#305EFF]"
                />
              </div>
              <div className="flex justify-between text-[10px] font-medium text-gray-400 mt-2">
                <span>5 units</span>
                <span>50 units</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="rounded-xl border border-[#305EFF]/15 bg-[#F6F8FD] p-3">
                <p className="text-[10px] uppercase tracking-wider font-bold text-[#305EFF] flex items-center gap-1"><TrendingUp className="w-3 h-3" /> Discount cap</p>
                <p className="text-lg font-black text-[#002155] mt-0.5 tabular-nums">{maxDiscount}%</p>
              </div>
              <div className="rounded-xl border border-[#305EFF]/15 bg-[#F6F8FD] p-3">
                <p className="text-[10px] uppercase tracking-wider font-bold text-[#305EFF] flex items-center gap-1"><Package className="w-3 h-3" /> Stock floor</p>
                <p className="text-lg font-black text-[#002155] mt-0.5 tabular-nums">{highStockThreshold} u</p>
              </div>
            </div>

            <button
              onClick={handleSavePolicy}
              className={`w-full font-bold py-3 rounded-xl text-sm flex items-center justify-center gap-2 transition-all shadow-sm ${
                saved
                  ? 'bg-emerald-500 text-white shadow-[0_4px_14px_-4px_rgba(16,185,129,0.5)]'
                  : 'bg-[#305EFF] text-white hover:bg-[#002155] shadow-[0_4px_14px_-4px_rgba(48,94,255,0.5)]'
              }`}
            >
              {saved
                ? <><Check className="w-4 h-4" /> Policy Applied to Agent</>
                : <>Apply Policy to AI Agent <ArrowUpRight className="w-4 h-4" /></>}
            </button>
          </div>
        </div>

        {/* Live Inventory Editor */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-[0_4px_24px_-12px_rgba(0,33,85,0.10)] hover:shadow-[0_6px_28px_-12px_rgba(48,94,255,0.20)] transition-shadow overflow-hidden">
          <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 text-[#305EFF]">
              <Database className="w-3.5 h-3.5" /> Live SKU Inventory
            </h3>
            <span className="text-[10px] font-bold text-[#002155] bg-[#F6F8FD] border border-[#305EFF]/15 rounded-full px-2.5 py-0.5">
              Real-time
            </span>
          </div>
          <div className="p-6 space-y-3 max-h-[460px] overflow-y-auto">
            {config.catalog.map((item: any) => {
              const stock = stockEdits[item.sku] ?? item.in_stock;
              const isLow = stock <= config.policy.high_stock_threshold;
              const isOut = stock <= 0;
              return (
                <div
                  key={item.sku}
                  className={`rounded-xl border p-3.5 transition-all ${
                    isOut ? 'border-red-200 bg-red-50/40'
                    : isLow ? 'border-[#0096FF]/30 bg-[#0096FF]/5'
                    : 'border-gray-100 bg-[#F6F8FD]/60 hover:border-[#305EFF]/30'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2.5">
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold text-[#002155] truncate">{item.name}</p>
                      <p className="text-[10px] font-mono text-gray-500 mt-0.5">{item.sku}</p>
                    </div>
                    {isOut ? (
                      <span className="text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider bg-red-100 text-red-700">
                        Out
                      </span>
                    ) : isLow ? (
                      <span className="text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider bg-[#0096FF]/15 text-[#005580]">
                        Low
                      </span>
                    ) : (
                      <span className="text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider bg-emerald-100 text-emerald-700">
                        In Stock
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <input
                        type="number"
                        min="0"
                        value={stockEdits[item.sku] ?? item.in_stock}
                        onChange={e => setStockEdits(prev => ({ ...prev, [item.sku]: Number(e.target.value) }))}
                        className="w-full border border-gray-200 rounded-lg pl-3 pr-3 py-2 text-sm font-mono bg-white text-[#002155] focus:outline-none focus:border-[#305EFF] focus:ring-2 focus:ring-[#305EFF]/20 transition-all tabular-nums"
                      />
                    </div>
                    <button
                      onClick={() => handleSaveStock(item.sku)}
                      className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 text-white ${
                        stockSaved[item.sku]
                          ? 'bg-emerald-500'
                          : 'bg-[#305EFF] hover:bg-[#002155]'
                      }`}
                    >
                      {stockSaved[item.sku] ? <><Check className="w-3 h-3" /> Saved</> : 'Update'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* AI Campaign Orchestrator */}
      <div className="bg-white border border-gray-100 rounded-2xl shadow-[0_4px_24px_-12px_rgba(0,33,85,0.10)] overflow-hidden">
        <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 text-[#305EFF]">
            <Sparkles className="w-3.5 h-3.5" /> AI Campaign Orchestrator
          </h3>
          <span className="text-[10px] font-bold text-[#002155] bg-[#F6F8FD] border border-[#305EFF]/15 rounded-full px-2.5 py-0.5 flex items-center gap-1">
            <Tag className="w-3 h-3" /> NL → Bounded Rules
          </span>
        </div>
        <div className="p-6 space-y-5">

        <div className="flex gap-3">
          <input
            type="text"
            value={campaignPrompt}
            onChange={e => setCampaignPrompt(e.target.value)}
            placeholder="e.g. 'Run a weekend flash sale on accessories, 20% off everything in the hoodie category'"
            className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-[#305EFF] focus:ring-1 focus:ring-[#305EFF] text-[#002155]"
          />
          <button
            onClick={handleGenerateCampaign}
            disabled={isGenerating}
            className="bg-[#305EFF] text-white px-6 py-3 rounded-xl text-sm font-bold shadow-sm hover:bg-[#002155] transition-colors whitespace-nowrap disabled:opacity-70"
          >
            {isGenerating ? 'Generating...' : 'Generate Rules'}
          </button>
        </div>

        {generatedCampaign && (
          <div className="mt-4 p-5 rounded-xl border border-[#305EFF]/20 bg-[#F6F8FD] space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="font-bold text-[#002155]">{generatedCampaign.name}</h4>
                <p className="text-xs text-[#305EFF] font-bold mt-1">Target: {generatedCampaign.target_category.toUpperCase()}</p>
              </div>
              <span className="bg-green-100 text-green-700 text-[10px] font-black px-2 py-1 rounded uppercase tracking-wider">
                Bounded & Gated
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white p-3 rounded-lg border border-gray-100">
                <p className="text-[10px] text-gray-500 font-bold uppercase">Discount Rule</p>
                <p className="text-lg font-black text-[#002155]">{generatedCampaign.discount_pct}% OFF</p>
              </div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-gray-100">
              <p className="text-[10px] text-gray-500 font-bold uppercase mb-1">Generated Marketing Copy</p>
              <p className="text-sm text-gray-700 italic">"{generatedCampaign.marketing_copy}"</p>
            </div>

            <button
              onClick={handleApplyCampaign}
              className={`w-full py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-colors text-white ${campaignSaved ? 'bg-green-600' : 'bg-[#002155] hover:bg-[#305EFF]'}`}
            >
              {campaignSaved ? <><Check className="w-4 h-4"/> Campaign Live</> : "Approve & Activate Campaign"}
            </button>
          </div>
        )}

        {config?.campaigns?.length > 0 && (
          <div className="mt-6 space-y-3">
            <h4 className="font-bold text-xs uppercase tracking-wider text-[#002155]">Active Campaigns</h4>
            {config.campaigns.map((camp: any, i: number) => (
              <div key={i} className="flex justify-between items-center bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
                <div>
                  <p className="font-bold text-[#305EFF]">{camp.name} <span className="text-gray-500 text-xs">({camp.discount_pct}% OFF)</span></p>
                  <p className="text-xs text-gray-500 font-mono mt-1">Target: {camp.target_sku && camp.target_sku !== 'NONE' ? camp.target_sku : (camp.target_category || 'all').toUpperCase()}</p>
                </div>
                <button onClick={() => handleDeleteCampaign(camp.name)} className="text-red-500 hover:bg-red-50 p-2 rounded-lg transition-colors">
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
