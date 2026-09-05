from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers import catalog, mandate, payments, storefront, gateway, merchant_config, agents, approvals, payment_verify, discovery, buyer_agent_runner, voice_stt, agent_catalog

app = FastAPI(title="TrustRail API")


def _stringify_detail(detail) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        bits = []
        for e in detail:
            if isinstance(e, dict):
                loc = ".".join(str(p) for p in e.get("loc", []))
                msg = e.get("msg", "")
                bits.append(f"{loc}: {msg}" if loc else str(msg))
            else:
                bits.append(str(e))
        return "; ".join(bits)
    return str(detail)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    # Always return detail as a string so the front-end can render it
    # without producing "[object Object]" from a template literal.
    return JSONResponse(
        status_code=422,
        content={"detail": _stringify_detail(exc.errors())},
    )


from fastapi.exceptions import HTTPException as _HTTPException  # noqa: E402


@app.exception_handler(_HTTPException)
async def _http_exception_handler(request: Request, exc: _HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": _stringify_detail(exc.detail)},
    )

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
app.include_router(agent_catalog.router)

# Register the merchant's own server-side identity on startup, using the SAME
# Ed25519 keypair that signs the agent catalog and the settlement receipt, so
# the manifest pubkey round-trips through every signature check.
from app.core.agent_registry import register_agent_with_private_key
from app.services.b2b_settlement import _MERCHANT_PRIVATE_KEY
register_agent_with_private_key(
    "merchant_souledstole_01",
    "merchant",
    ["bulk_discount_negotiation", "inventory_check", "test_mode_payment"],
    _MERCHANT_PRIVATE_KEY,
)

@app.get("/")
def root():
    return {"status": "TrustRail Backend is live"}
