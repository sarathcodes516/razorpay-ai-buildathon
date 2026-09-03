import os
import json
from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI
from app.core.merchant_state import get_store_state, update_store_policy, update_inventory, set_active_campaign

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

Respond ONLY in JSON matching this schema:
{{
  "name": "Catchy Campaign Name",
  "discount_pct": <float>,
  "budget_limit": <float>,
  "target_category": "apparel" | "accessories" | "all",
  "target_sku": "SKU_CODE" | "NONE",
  "marketing_copy": "A short, punchy 1-sentence SMS/Email blast."
}}"""

    response = client.chat.completions.create(
        model="minimax/minimax-m3:free",
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
    return set_active_campaign(req.model_dump())