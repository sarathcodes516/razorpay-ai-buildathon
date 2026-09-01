import json
import os
from fastapi import APIRouter

router = APIRouter()

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "../data/catalog.json")

@router.get("/api/catalog")
def get_catalog():
    with open(CATALOG_PATH, "r") as f:
        return json.load(f)
