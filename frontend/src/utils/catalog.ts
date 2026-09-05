/**
 * catalog.ts — shared catalog helpers.
 *
 * Maps a SKU to the local product image (in /public) and exposes a tiny helper
 * for the chatbot to render a product chip strip right below an agent message.
 */

export type CatalogItem = {
  sku: string;
  name: string;
  price: number;
  category: string;
  in_stock: number;
  image?: string;
};

/**
 * SKU → local /public image path.
 * The backend seeds these five SKUs (see backend/app/core/merchant_state.py).
 */
const IMAGE_BY_SKU: Record<string, string> = {
  "TEE-001": "/Cyberpunk Oversized Graphic Tee.png",
  "HOD-002": "/Tokyo Drift Heavyweight Hoodie.png",
  "CRG-003": "/Utility Cargo Pants V2.png",
  "ACC-004": "/Tactical Crossbody Bag.png",
  "ACC-005": "/Classic Logo Beanie.png",
};

/** Fallback image when a SKU is missing from the map. */
const FALLBACK_IMAGE = "/logo.png";

export function imageFor(sku: string): string {
  return IMAGE_BY_SKU[sku] ?? FALLBACK_IMAGE;
}

/**
 * Look up a single SKU in a catalog list. Returns undefined if the SKU
 * isn't present (caller decides how to handle the miss).
 */
export function findInCatalog(
  catalog: CatalogItem[],
  sku: string,
): CatalogItem | undefined {
  return catalog.find((i) => i.sku === sku);
}

/**
 * Compute the effective price for a SKU after applying the best
 * active campaign (mirror of the backend's logic, so the chat chip
 * matches the Razorpay order total the server will compute).
 */
export function effectivePrice(
  item: CatalogItem,
  activeCampaigns: { target_sku?: string; target_category?: string; discount_pct: number }[],
): { original: number; final: number; pct: number } {
  const original = Number(item.price) || 0;
  let bestPct = 0;
  for (const c of activeCampaigns) {
    if (!c || !c.discount_pct) continue;
    const eligible =
      (c.target_sku && c.target_sku !== "NONE" && c.target_sku === item.sku) ||
      (!c.target_sku || c.target_sku === "NONE"
        ? c.target_category === "all" || c.target_category === item.category
        : false);
    if (eligible && c.discount_pct > bestPct) bestPct = c.discount_pct;
  }
  const final = Math.max(0, original * (1 - bestPct / 100));
  return { original, final, pct: bestPct };
}
