import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Sliders, Database, Check } from 'lucide-react';

const API = 'http://localhost:8001';
const MERCHANT_BLUE = '#0E54CD';

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
    setConfig((prev: any) => ({ ...prev, active_campaign: generatedCampaign }));
    setCampaignSaved(true);
    setTimeout(() => setCampaignSaved(false), 2000);
  };

  if (!config) return (
    <div className="max-w-4xl mx-auto p-8 text-sm text-gray-500">
      Loading dynamic merchant parameters...
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Header — merchant blue accent */}
      <div className="bg-white rounded-2xl p-6 shadow-sm" style={{ border: `2px solid ${MERCHANT_BLUE}` }}>
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl" style={{ backgroundColor: `${MERCHANT_BLUE}18`, color: MERCHANT_BLUE }}>
            <Sliders className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-gray-900">Merchant Runtime Policy Engine</h2>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase text-white" style={{ backgroundColor: MERCHANT_BLUE }}>
                Seller Side
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Modify store rules live. The AI Merchant Agent reads this state on every negotiation turn — no restart needed.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Policy Sliders */}
        <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm space-y-5">
          <h3 className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5" style={{ color: MERCHANT_BLUE }}>
            <Sliders className="w-3.5 h-3.5" /> Store Margin Rules
          </h3>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-bold text-gray-700">Max Allowable Discount</label>
              <span className="text-sm font-black font-mono" style={{ color: MERCHANT_BLUE }}>{maxDiscount}%</span>
            </div>
            <input
              type="range" min="5" max="40" step="5"
              value={maxDiscount}
              onChange={e => setMaxDiscount(Number(e.target.value))}
              className="w-full cursor-pointer"
              style={{ accentColor: MERCHANT_BLUE }}
            />
            <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
              <span>5% (tight margins)</span>
              <span>40% (clearance)</span>
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-bold text-gray-700">High Stock Threshold</label>
              <span className="text-sm font-black font-mono" style={{ color: MERCHANT_BLUE }}>{highStockThreshold} units</span>
            </div>
            <input
              type="range" min="5" max="50" step="5"
              value={highStockThreshold}
              onChange={e => setHighStockThreshold(Number(e.target.value))}
              className="w-full cursor-pointer"
              style={{ accentColor: MERCHANT_BLUE }}
            />
            <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
              <span>5 units</span>
              <span>50 units</span>
            </div>
          </div>

          <div className="pt-2 border-t border-gray-100">
            <div className="rounded-lg p-3 text-xs font-mono space-y-1 mb-4" style={{ backgroundColor: `${MERCHANT_BLUE}08`, border: `1px solid ${MERCHANT_BLUE}30` }}>
              <div style={{ color: MERCHANT_BLUE }} className="font-bold">merchant_policy:</div>
              <div className="pl-2 text-gray-600">max_discount: <span className="font-bold" style={{ color: MERCHANT_BLUE }}>{maxDiscount}%</span></div>
              <div className="pl-2 text-gray-600">high_stock_threshold: <span className="font-bold" style={{ color: MERCHANT_BLUE }}>{highStockThreshold} units</span></div>
            </div>
            <button
              onClick={handleSavePolicy}
              className="w-full text-white font-bold py-2.5 rounded-xl text-sm flex items-center justify-center gap-2 transition-all shadow-sm"
              style={{ backgroundColor: saved ? '#16a34a' : MERCHANT_BLUE }}
            >
              {saved ? <><Check className="w-4 h-4" /> Policy Applied to Agent</> : "Apply Policy to AI Agent"}
            </button>
          </div>
        </div>

        {/* Live Inventory Editor */}
        <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5" style={{ color: MERCHANT_BLUE }}>
            <Database className="w-3.5 h-3.5" /> Live SKU Inventory Editor
          </h3>
          <p className="text-xs text-gray-500">
            Change stock levels to trigger different agent discount behaviors in real time.
          </p>
          <div className="space-y-3">
            {config.catalog.map((item: any) => {
              const stock = stockEdits[item.sku] ?? item.in_stock;
              const isLow = stock <= config.policy.high_stock_threshold;
              return (
                <div key={item.sku} className="rounded-xl border p-3" style={{
                  borderColor: isLow ? '#f97316' : '#e5e7eb',
                  backgroundColor: isLow ? '#fff7ed' : '#f9fafb'
                }}>
                  <div className="flex justify-between items-center mb-2">
                    <div>
                      <p className="text-xs font-bold text-gray-800 truncate max-w-[160px]">{item.name}</p>
                      <p className="text-[10px] font-mono text-gray-400">{item.sku}</p>
                    </div>
                    {isLow && (
                      <span className="text-[10px] bg-orange-200 text-orange-800 font-bold px-2 py-0.5 rounded uppercase">
                        Low Stock
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      value={stockEdits[item.sku] ?? item.in_stock}
                      onChange={e => setStockEdits(prev => ({ ...prev, [item.sku]: Number(e.target.value) }))}
                      className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm font-mono bg-white focus:outline-none"
                      style={{ outlineColor: MERCHANT_BLUE }}
                    />
                    <button
                      onClick={() => handleSaveStock(item.sku)}
                      className="px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 text-white"
                      style={{ backgroundColor: stockSaved[item.sku] ? '#16a34a' : MERCHANT_BLUE }}
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
      <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm space-y-5">
        <h3 className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 text-[#305EFF]">
          <Sliders className="w-3.5 h-3.5" /> AI Campaign Orchestrator
        </h3>
        <p className="text-xs text-gray-500">
          Instruct the AI to build a strictly bounded promotional campaign. This state will be synced to the B2C chatbot immediately.
        </p>

        <div className="flex gap-3">
          <input
            type="text"
            value={campaignPrompt}
            onChange={e => setCampaignPrompt(e.target.value)}
            placeholder="e.g. 'Run a weekend flash sale on accessories, cap the budget at ₹5000'"
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
              <div className="bg-white p-3 rounded-lg border border-gray-100">
                <p className="text-[10px] text-gray-500 font-bold uppercase">Budget Cap</p>
                <p className="text-lg font-black text-red-600 font-mono">₹{generatedCampaign.budget_limit}</p>
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
      </div>
    </div>
  );
}
