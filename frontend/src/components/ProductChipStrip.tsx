import React from 'react';
import type { CatalogItem } from '../utils/catalog';
import { imageFor, effectivePrice } from '../utils/catalog';

interface ProductChipStripProps {
  /** SKUs the agent just mentioned (deduped upstream). */
  skus: string[];
  catalog: CatalogItem[];
  activeCampaigns: { target_sku?: string; target_category?: string; discount_pct: number }[];
  onViewSku: (sku: string) => void;
}

/**
 * Horizontal strip of compact product chips that renders just below an agent
 * message. Each chip shows image / name / current price (or "out of stock").
 * Clicking flips the active tab to the catalog and scrolls the card into view.
 */
export function ProductChipStrip({
  skus,
  catalog,
  activeCampaigns,
  onViewSku,
}: ProductChipStripProps) {
  if (!skus || skus.length === 0) return null;

  const items = skus
    .map((sku) => catalog.find((c) => c.sku === sku))
    .filter((c): c is CatalogItem => Boolean(c));

  if (items.length === 0) return null;

  return (
    <div className="mt-2 w-full max-w-full min-w-0">
      <div className="flex items-center justify-between mb-1.5">
        <p className="text-[9px] font-bold uppercase tracking-widest text-[#305EFF]">
          Mentioned in this reply
        </p>
        {items.length > 1 && (
          <p className="text-[9px] font-mono text-[#0096FF] flex items-center gap-0.5">
            swipe <span aria-hidden>→</span>
          </p>
        )}
      </div>
      <div className="relative">
        <div
          className="flex gap-2 overflow-x-auto pb-3 -mx-1 px-1 snap-x snap-mandatory"
          style={{ scrollbarWidth: "thin" } as React.CSSProperties}
        >
        {items.map((item) => {
          const { original, final, pct } = effectivePrice(
            item,
            activeCampaigns,
          );
          const outOfStock = item.in_stock <= 0;
          return (
            <button
              key={item.sku}
              type="button"
              onClick={() => onViewSku(item.sku)}
              className="group flex-shrink-0 w-44 snap-start bg-white border border-[#305EFF]/25 rounded-xl overflow-hidden text-left hover:border-[#305EFF] hover:shadow-md transition-all"
            >
              <div className="relative aspect-[4/3] bg-gray-100 overflow-hidden">
                <img
                  src={imageFor(item.sku)}
                  alt={item.name}
                  className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).src = "/logo.png";
                  }}
                />
                {pct > 0 && (
                  <div className="absolute top-1.5 left-1.5 bg-[#EC2D37] text-white text-[9px] font-black px-1.5 py-0.5 rounded">
                    -{pct}%
                  </div>
                )}
                {outOfStock && (
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                    <span className="text-white text-[10px] font-black uppercase tracking-widest">
                      Out
                    </span>
                  </div>
                )}
              </div>
              <div className="px-2.5 py-2">
                <p className="text-[11px] font-semibold text-[#002155] truncate">
                  {item.name}
                </p>
                <p className="text-[9px] font-mono text-gray-400">
                  {item.sku}
                </p>
                <div className="flex items-baseline gap-1.5 mt-0.5">
                  <p className="text-xs font-black text-[#305EFF]">
                    ₹{final.toLocaleString()}
                  </p>
                  {pct > 0 && (
                    <p className="text-[10px] text-gray-400 line-through">
                      ₹{original.toLocaleString()}
                    </p>
                  )}
                </div>
                <p className="text-[9px] font-semibold text-[#0096FF] mt-0.5 flex items-center gap-0.5">
                  View in catalog →
                </p>
              </div>
            </button>
          );
        })}
        </div>
        {items.length > 1 && (
          <div
            className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-white to-transparent"
            aria-hidden="true"
          />
        )}
      </div>
    </div>
  );
}
