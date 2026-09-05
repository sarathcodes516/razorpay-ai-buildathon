"""
b2c_intent_gate.py — Server-authoritative intent classifier.

The LLM emits `internal_intent` freely. We never trust it as-is for checkout,
because a hostile or simply eager model can fire checkout on any positive
phrase ("add it", "yeah", "sure"). This module provides a small, deterministic
regex + token classifier the router runs AFTER the LLM, before honouring
checkout or BUY. Keeps the LLM prompt unchanged.
"""
from __future__ import annotations

import re
from typing import Iterable


# Tight, exhaustive list of phrases that genuinely mean "go to payment".
# Pure regex on the user's message — no LLM involvement.
_CHECKOUT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(check\s*out|checkout)\b", re.IGNORECASE),
    re.compile(r"\b(pay\s*now|pay\s*it|pay\s*for\s*it|pay\s*today)\b", re.IGNORECASE),
    re.compile(r"\b(proceed\s*to\s*payment|take\s*me\s*to\s*payment)\b", re.IGNORECASE),
    re.compile(r"\b(place\s*(the\s*)?order|place\s*my\s*order)\b", re.IGNORECASE),
    re.compile(r"\b(complete\s*(the\s*)?purchase|complete\s*my\s*order)\b", re.IGNORECASE),
    re.compile(r"\b(buy\s*it\s*now|buy\s*now)\b", re.IGNORECASE),
    re.compile(r"\b(i'?m\s*done|i\s*am\s*done|that'?s\s*all|that\s*is\s*all|nothing\s*else|no\s*more|done\s*shopping|wrap\s*it\s*up)\b", re.IGNORECASE),
    re.compile(r"\b(send\s*me\s*the\s*(payment|receipt)|finalize)\b", re.IGNORECASE),
    re.compile(r"\b(make\s*it\s*happen|let'?s\s*go)\b", re.IGNORECASE),
)

# Words/phrases that DO NOT count as checkout on their own. The LLM has a
# habit of treating these as "BUY → checkout". They should be classified BUY.
_BUY_FLOOR = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "k", "kk",
    "add", "added", "add it", "add them", "include it", "throw it in",
    "toss it in", "i'll take it", "ill take it", "i want it", "i want that",
    "do it", "go ahead", "please", "confirm", "fine", "alright", "cool",
}


def is_checkout_intent(user_message: str) -> bool:
    """True only when the user's own words clearly request payment."""
    if not user_message:
        return False
    msg = user_message.strip().lower()
    if any(p.search(msg) for p in _CHECKOUT_PATTERNS):
        return True
    return False


def looks_like_acceptance(user_message: str) -> bool:
    """True when the user is agreeing to a previous suggestion.

    Used server-side to drive the follow-up re-pitch after a successful add
    so the conversation keeps selling without waiting for the LLM to remember.
    """
    if not user_message:
        return False
    cleaned = re.sub(r"[^\w\s']", " ", user_message.strip().lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return False
    if cleaned in _BUY_FLOOR:
        return True
    tokens = cleaned.split()
    if len(tokens) <= 4:
        if all(t in _BUY_FLOOR for t in tokens):
            return True
    if cleaned.startswith(("add ", "i want", "i'll take", "ill take", "i will take", "throw ", "toss ", "include ", "do it", "go ahead", "yes ", "yeah ", "yep ", "yup ", "sure ", "ok ", "okay ")):
        return True
    if re.match(r"^(yes|yeah|yep|yup|sure|ok|okay|k|kk|alright|cool|fine|do it|please)(\s|$)", cleaned):
        return True
    return False


def normalize_intent(llm_intent: str, user_message: str, cart_is_empty: bool) -> str:
    """
    Coerce the LLM's `internal_intent` to one of BUY / QUESTION / CHECKOUT /
    GENERAL using deterministic rules:

      - CHECKOUT only if `is_checkout_intent(user_message)` AND cart non-empty.
      - BUY if `looks_like_acceptance(user_message)` or the LLM said BUY.
      - QUESTION if the message contains a question mark and isn't a CHECKOUT.
      - GENERAL otherwise (including the LLM spuriously saying CHECKOUT).
    """
    if cart_is_empty and (llm_intent or "").upper() == "CHECKOUT":
        return "GENERAL"
    if is_checkout_intent(user_message) and not cart_is_empty:
        return "CHECKOUT"
    upper = (llm_intent or "GENERAL").upper()
    if upper in ("BUY", "QUESTION", "CHECKOUT", "GENERAL"):
        if upper == "CHECKOUT":
            return "BUY" if looks_like_acceptance(user_message) else "GENERAL"
        return upper
    return "GENERAL"


def next_best_pitch_sku(
    annotated_catalog: Iterable[dict],
    current_cart_skus: set[str],
    just_added_sku: str | None,
) -> str | None:
    """
    Pick the single most attractive next SKU to upsell/cross-sell after the
    user just accepted a suggestion. Pure deterministic ranking — no LLM.

    Strategy:
      - Exclude items already in the cart and the item just added.
      - First priority: items with active campaigns. Only pitch campaign items
        until the user has all campaign-eligible items in cart.
      - Second priority: all other in-stock items.
      - Score = effective_price * (best_discount_pct / 100 + 0.1), multiplied
        by 5.0 when the candidate has an active campaign, and by an additional
        3.0 when the candidate shares the same category as the just-added
        item. This strongly prefers same-category upsells over unrelated
        high-price cross-sells.
      - Ties broken by category diversity: prefer a different category from
        `just_added_sku` (cross-sell) over the same one (upsell).
    """
    catalog = [c for c in annotated_catalog if c.get("sku") and int(c.get("in_stock", 0)) > 0]
    if not catalog:
        return None
    just_meta = next((c for c in catalog if c.get("sku") == just_added_sku), None)
    just_cat = (just_meta or {}).get("category")

    def score(c: dict) -> float:
        price = float(c.get("effective_price", c.get("price", 0.0)) or 0.0)
        pct = float(c.get("best_discount_pct", 0.0) or 0.0)
        cat = c.get("category", "")
        has_campaign = bool((c.get("eligible_campaigns") or []))
        base = price * (pct / 100.0 + 0.1)
        if just_cat and cat == just_cat:
            base *= 3.0
        if has_campaign:
            base *= 5.0
        return base

    candidates = [
        c for c in catalog
        if c.get("sku") not in current_cart_skus and c.get("sku") != just_added_sku
    ]
    if not candidates:
        return None

    campaign_items = [c for c in candidates if (c.get("eligible_campaigns") or [])]
    non_campaign_items = [c for c in candidates if not (c.get("eligible_campaigns") or [])]

    def pick_best(pool: list[dict]) -> str | None:
        if not pool:
            return None
        same_cat = [c for c in pool if c.get("category") == just_cat]
        cross_cat = [c for c in pool if c.get("category") != just_cat]

        best_same = max(same_cat, key=score) if same_cat else None
        best_cross = max(cross_cat, key=score) if cross_cat else None

        if best_same and best_cross:
            score_same = score(best_same)
            score_cross = score(best_cross)
            if score_cross >= score_same * 0.7:
                return best_cross["sku"]
            return best_same["sku"]
        if best_same:
            return best_same["sku"]
        if best_cross:
            return best_cross["sku"]
        return None

    best = pick_best(campaign_items)
    if best:
        return best
    return pick_best(non_campaign_items)