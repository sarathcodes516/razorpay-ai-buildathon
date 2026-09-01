# Dynamic Store State — mutable at runtime by judges via /api/merchant/* endpoints
STORE_STATE = {
    "store_name": "The Souled Stole",
    "policy": {
        "max_allowable_discount_pct": 15.0,
        "high_stock_threshold": 20,
        "high_stock_bonus_discount_pct": 5.0
    },
    "catalog": [
        {
            "sku": "TEE-001",
            "name": "Cyberpunk Oversized Graphic Tee",
            "price": 999.0,
            "category": "apparel",
            "in_stock": 50
        },
        {
            "sku": "HOD-002",
            "name": "Tokyo Drift Heavyweight Hoodie",
            "price": 1999.0,
            "category": "apparel",
            "in_stock": 12  # Low stock scenario
        },
        {
            "sku": "CRG-003",
            "name": "Utility Cargo Pants V2",
            "price": 1499.0,
            "category": "apparel",
            "in_stock": 25
        },
        {
            "sku": "ACC-004",
            "name": "Tactical Crossbody Bag",
            "price": 799.0,
            "category": "accessories",
            "in_stock": 30
        },
        {
            "sku": "ACC-005",
            "name": "Classic Logo Beanie",
            "price": 499.0,
            "category": "accessories",
            "in_stock": 100
        }
    ]
}


def get_store_state() -> dict:
    return STORE_STATE


def update_store_policy(new_policy: dict) -> dict:
    STORE_STATE["policy"].update(new_policy)
    return STORE_STATE["policy"]


def update_inventory(sku: str, stock: int) -> list:
    for item in STORE_STATE["catalog"]:
        if item["sku"] == sku:
            item["in_stock"] = stock
            break
    return STORE_STATE["catalog"]
