import React from 'react';
import type { CatalogItem } from '../utils/catalog';
import { imageFor, effectivePrice } from '../utils/catalog';

interface ProductGridProps {
  catalog: CatalogItem[];
  activeCampaigns: { target_sku?: string; target_category?: string; discount_pct: number }[];
  /** Currently highlighted SKU (e.g. customer clicked a chat chip). */
  highlightSku?: string | null;
  /** Click handler — receives the SKU. App.tsx uses this to switch tabs + scroll. */
  onViewSku?: (sku: string) => void;
}

export default function ProductGrid({
  catalog,
  activeCampaigns,
  highlightSku,
  onViewSku,
}: ProductGridProps) {
  return (
    <div className="max-w-screen-xl mx-auto px-6 py-10">
      <h2 className="text-center text-xl font-black tracking-widest text-gray-900 mb-8 uppercase">
        New Arrivals
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {catalog.map((item) => {
          const { original, final, pct } = effectivePrice(item, activeCampaigns);
          const hasDiscount = pct > 0;
          const highlighted = highlightSku === item.sku;
          return (
            <div
              key={item.sku}
              onClick={() => onViewSku?.(item.sku)}
              className={`group cursor-pointer transition-all rounded-md p-2 ${
                highlighted
                  ? "ring-2 ring-[#305EFF] ring-offset-2 ring-offset-[#F6F8FD] bg-white"
                  : "hover:bg-white/60"
              }`}
            >
              <div className="relative aspect-[3/4] bg-gray-100 overflow-hidden mb-3 rounded-md">
                <img
                  src={imageFor(item.sku)}
                  alt={item.name}
                  className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).src = "/logo.png";
                  }}
                />
                {hasDiscount ? (
                  <div className="absolute top-2 left-2 bg-[#EC2D37] text-white text-[10px] font-black px-2 py-1 uppercase rounded-sm">
                    -{pct}% OFF
                  </div>
                ) : (
                  <div className="absolute top-2 left-2 bg-black/80 text-white text-[10px] font-bold px-2 py-1 uppercase rounded-sm">
                    New Drop
                  </div>
                )}
                <div className="absolute top-2 right-2 bg-white/90 backdrop-blur text-[#002155] text-[10px] font-mono px-1.5 py-0.5 rounded">
                  {item.sku}
                </div>
              </div>
              <h3 className="text-sm font-semibold text-gray-900 truncate">
                {item.name}
              </h3>
              <p className="text-xs text-gray-500 mb-1 capitalize">
                {item.category}
              </p>
              <div className="flex items-baseline gap-2">
                <p className="text-sm font-bold text-gray-900">
                  ₹ {final.toLocaleString()}
                </p>
                {hasDiscount && (
                  <p className="text-xs text-gray-400 line-through">
                    ₹ {original.toLocaleString()}
                  </p>
                )}
              </div>
              <p
                className={`text-[10px] mt-1 font-semibold ${
                  item.in_stock <= 0
                    ? "text-red-600"
                    : item.in_stock <= 10
                    ? "text-orange-500"
                    : "text-emerald-600"
                }`}
              >
                {item.in_stock <= 0
                  ? "Out of stock"
                  : item.in_stock <= 10
                  ? `Only ${item.in_stock} left`
                  : "In stock"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
