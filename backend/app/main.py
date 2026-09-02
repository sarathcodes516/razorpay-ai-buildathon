from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import catalog, mandate, payments, storefront, gateway, merchant_config, agents, approvals, payment_verify, discovery, buyer_agent_runner, voice_stt

app = FastAPI(title="TrustRail API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3003",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3003",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(mandate.router)
app.include_router(payments.router)
app.include_router(storefront.router)
app.include_router(gateway.router) # Face 2 Router included!
app.include_router(merchant_config.router)
app.include_router(agents.router)
app.include_router(approvals.router)
app.include_router(payment_verify.router)
app.include_router(discovery.router)
app.include_router(buyer_agent_runner.router)
app.include_router(voice_stt.router)

# Register the merchant's own server-side identity on startup
from app.core.agent_registry import register_agent as _register_agent
_register_agent(
    "merchant_souledstole_01",
    "merchant",
    ["bulk_discount_negotiation", "inventory_check", "test_mode_payment"],
)

@app.get("/")
def root():
    return {"status": "TrustRail Backend is live"}
