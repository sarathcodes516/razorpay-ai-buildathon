from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import catalog, mandate, payments

app = FastAPI(title="TrustRail API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(mandate.router)
app.include_router(payments.router)

@app.get("/")
def root():
    return {"status": "TrustRail Backend is live"}
