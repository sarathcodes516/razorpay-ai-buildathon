from app.models.cart import CartMandate
from app.models.mandate import SpendMandate
from typing import Tuple, Dict

def check_against_mandate(cart: CartMandate, mandate: SpendMandate) -> Tuple[bool, str, Dict]:
    audit = {"step": "bounds_check", "cart_id": cart.cart_id}

    if cart.final_amount > mandate.limits.max_per_transaction:
        audit.update({"rule": "final_amount <= max_per_transaction", "evaluated": f"{cart.final_amount} <= {mandate.limits.max_per_transaction} -> FAIL", "action_taken": "ESCALATE_TO_HUMAN_APPROVAL"})
        return False, "ESCALATE", audit

    allowed = set(mandate.limits.allowed_categories)
    cart_cats = {item.category for item in cart.items}
    if not cart_cats.issubset(allowed):
        audit.update({"rule": "categories in allowed_categories", "evaluated": f"{cart_cats} in {allowed} -> FAIL", "action_taken": "REJECT_OUT_OF_BOUNDS"})
        return False, "REJECT", audit

    if cart.discount_pct > mandate.limits.max_discount_agent_can_accept_pct:
        audit.update({"rule": "discount <= max_discount", "evaluated": f"{cart.discount_pct} <= {mandate.limits.max_discount_agent_can_accept_pct} -> FAIL", "action_taken": "ESCALATE_TO_HUMAN_APPROVAL"})
        return False, "ESCALATE", audit

    if cart.final_amount <= mandate.limits.auto_approve_below:
        audit.update({"rule": "final_amount <= auto_approve_below", "evaluated": f"{cart.final_amount} <= {mandate.limits.auto_approve_below} -> PASS", "action_taken": "AUTO_APPROVE_TO_RAZORPAY"})
        return True, "EXECUTE", audit
    
    audit.update({"rule": "final_amount <= auto_approve_below", "evaluated": f"{cart.final_amount} <= {mandate.limits.auto_approve_below} -> FAIL", "action_taken": "ESCALATE_TO_HUMAN_APPROVAL"})
    return False, "ESCALATE", audit
