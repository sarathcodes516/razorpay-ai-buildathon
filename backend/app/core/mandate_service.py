import hmac
import hashlib
import json
from datetime import datetime
from app.models.mandate import SpendMandate

SECRET_KEY = b"trustrail_hackathon_secret_2026"

def sign_mandate(mandate_data: dict) -> str:
    payload = json.dumps(mandate_data, sort_keys=True).encode("utf-8")
    return hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest()

def create_mandate(principal: str, limits: dict) -> SpendMandate:
    mandate_id = f"man_{int(datetime.utcnow().timestamp())}"
    
    mandate_dict = {
        "mandate_id": mandate_id,
        "principal": principal,
        "issued_at": datetime.utcnow().isoformat(),
        "expires_at": "2026-12-31T23:59:59Z", 
        "limits": limits
    }
    
    signature = sign_mandate(mandate_dict)
    return SpendMandate(**mandate_dict, signature=signature)

def verify_mandate(mandate: SpendMandate) -> bool:
    mandate_dict = mandate.model_dump(exclude={"signature"})
    mandate_dict["issued_at"] = mandate.issued_at.isoformat()
    mandate_dict["expires_at"] = mandate.expires_at.isoformat()
    
    expected_signature = sign_mandate(mandate_dict)
    return hmac.compare_digest(expected_signature, mandate.signature)
