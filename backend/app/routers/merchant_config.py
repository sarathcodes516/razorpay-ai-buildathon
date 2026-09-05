import os
import json
from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI
from app.agents.llm_client import MODEL
from app.core.merchant_state import get_store_state, update_store_policy, update_inventory, set_active_campaign, add_campaign, remove_campaign

router = APIRouter()
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY", "dummy_key"))

class PolicyUpdate(BaseModel):
    max_allowable_discount_pct: float
    high_stock_threshold: int

class InventoryUpdate(BaseModel):
    sku: str
    in_stock: int

class CampaignPrompt(BaseModel):
    prompt: str

class CampaignApply(BaseModel):
    name: str
    discount_pct: float
    budget_limit: float
    target_category: str
    target_sku: str = "NONE"
    marketing_copy: str
    active: bool = True
    trigger_rule: str = "always"  # "always" | "low_stock" | "until_low_stock"

@router.get("/api/merchant/config")
def get_config():
    return get_store_state()

@router.post("/api/merchant/policy")
def set_policy(policy: PolicyUpdate):
    return update_store_policy(policy.model_dump())

@router.post("/api/merchant/inventory")
def set_inventory(inv: InventoryUpdate):
    return update_inventory(inv.sku, inv.in_stock)

@router.post("/api/merchant/campaign/generate")
def generate_campaign(req: CampaignPrompt):
    catalog = json.dumps(get_store_state()["catalog"])
    sys_prompt = f"""You are a B2B Campaign Orchestrator AI.
Catalog: {catalog}

Analyze the merchant's request and generate a STRICTLY BOUNDED promotional campaign.
CRITICAL: If the merchant targets a specific item, you MUST provide its exact SKU in `target_sku`.

TRIGGER RULE (CRITICAL): If the merchant's request mentions any of:
  - "until stock runs low", "until stock becomes lower", "while stock is high",
    "until we run out", "while we still have stock", "while still in stock"
  - similar phrases that tie the discount to current inventory levels
  then you MUST set `trigger_rule` to "until_low_stock" (apply while stock >= high_stock_threshold).

  - "low stock", "last few", "while supplies last", "when stock drops"
  then set `trigger_rule` to "low_stock" (apply only when stock has dropped below the threshold).

  Otherwise, set `trigger_rule` to "always" (default — applies regardless of stock level).

Respond ONLY in JSON matching this schema:
{{
  "name": "Catchy Campaign Name",
  "discount_pct": <float>,
  "budget_limit": <float>,
  "target_category": "apparel" | "accessories" | "all",
  "target_sku": "SKU_CODE" | "NONE",
  "trigger_rule": "always" | "low_stock" | "until_low_stock",
  "marketing_copy": "A short, punchy 1-sentence SMS/Email blast."
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": req.prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail={"error": "llm_returned_invalid_json", "raw": raw[:500]})

@router.post("/api/merchant/campaign/apply")
def apply_campaign(req: CampaignApply):
    return add_campaign(req.model_dump())

@router.delete("/api/merchant/campaign/{campaign_name}")
def delete_campaign(campaign_name: str):
    return remove_campaign(campaign_name)