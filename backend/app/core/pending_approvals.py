PENDING_APPROVALS: dict[str, dict] = {}


def store_pending(cart_id: str, cart, mandate_id: str, audit: dict):
    PENDING_APPROVALS[cart_id] = {"cart": cart, "mandate_id": mandate_id, "audit": audit}


def pop_pending(cart_id: str):
    return PENDING_APPROVALS.pop(cart_id, None)
