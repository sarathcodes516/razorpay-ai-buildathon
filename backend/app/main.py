from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import catalog, mandate

app = FastAPI(title="TrustRail API")

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For hackathon dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(catalog.router)
app.include_router(mandate.router)

@app.get("/")
def root():
    return {"status": "TrustRail Backend is live"}
