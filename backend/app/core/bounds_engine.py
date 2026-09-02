from datetime import datetime, timezone
from app.core.spend_ledger import get_spent_today


def check_against_mandate(cart, mandate):
    audit = {"step": "bounds_check", "cart_id": cart.cart_id}

    # Rule 0: Mandate expiry
    expires = (
        mandate.expires_at
        if mandate.expires_at.tzinfo
        else mandate.expires_at.replace(tzinfo=timezone.utc)
    )
    if expires < datetime.now(timezone.utc):
        audit.update({
            "rule": "mandate not expired",
            "evaluated": f"expired_at={mandate.expires_at} -> FAIL",
            "action_taken": "REJECT_EXPIRED_MANDATE"
        })
        return False, "REJECT", audit

    # Rule 1: Single transaction ceiling
    if cart.final_amount > mandate.limits.max_per_transaction:
        audit.update({
            "rule": "final_amount <= max_per_transaction",
            "evaluated": f"{cart.final_amount} <= {mandate.limits.max_per_transaction} -> FAIL",
            "action_taken": "ESCALATE_TO_HUMAN_APPROVAL"
        })
        return False, "ESCALATE", audit

    # Rule 2: Category allowlist
    allowed = set(mandate.limits.allowed_categories)
    cats = {i.category for i in cart.items}
    if not cats.issubset(allowed):
        audit.update({
            "rule": "categories in allowed_categories",
            "evaluated": f"{cats} not subset of {allowed} -> FAIL",
            "action_taken": "REJECT_OUT_OF_BOUNDS"
        })
        return False, "REJECT", audit

    # Rule 3: Cumulative daily spend limit
    spent = get_spent_today(mandate.mandate_id)
    projected = spent + cart.final_amount
    if projected > mandate.limits.max_total_spend_today:
        audit.update({
            "rule": "spent_today + final_amount <= max_total_spend_today",
            "evaluated": f"{spent} + {cart.final_amount} = {projected} > {mandate.limits.max_total_spend_today} -> FAIL",
            "action_taken": "REJECT_DAILY_BUDGET_EXCEEDED"
        })
        return False, "REJECT", audit

    # Rule 4a: Anomaly discount threshold (optional — escalate for human review)
    if (mandate.limits.anomaly_discount_threshold_pct is not None
            and cart.discount_pct > mandate.limits.anomaly_discount_threshold_pct):
        audit.update({
            "rule": "discount_pct <= anomaly_discount_threshold_pct",
            "evaluated": f"{cart.discount_pct} > {mandate.limits.anomaly_discount_threshold_pct} -> FLAGGED",
            "action_taken": "ESCALATE_ANOMALY_REVIEW"
        })
        return False, "ESCALATE", audit

    # Rule 4b: Hard discount ceiling
    if cart.discount_pct > mandate.limits.max_discount_agent_can_accept_pct:
        audit.update({
            "rule": "discount_pct <= max_discount_agent_can_accept_pct",
            "evaluated": f"{cart.discount_pct} > {mandate.limits.max_discount_agent_can_accept_pct} -> FAIL",
            "action_taken": "ESCALATE_TO_HUMAN_APPROVAL"
        })
        return False, "ESCALATE", audit

    # Rule 5: Auto-approve line
    if cart.final_amount <= mandate.limits.auto_approve_below:
        audit.update({
            "rule": "final_amount <= auto_approve_below",
            "evaluated": f"{cart.final_amount} <= {mandate.limits.auto_approve_below} -> PASS",
            "action_taken": "AUTO_APPROVE_TO_RAZORPAY"
        })
        return True, "EXECUTE", audit

    # Fallback: valid cart but above auto-approve, needs human sign-off
    audit.update({
        "rule": "final_amount <= auto_approve_below",
        "evaluated": f"{cart.final_amount} <= {mandate.limits.auto_approve_below} -> FAIL",
        "action_taken": "ESCALATE_TO_HUMAN_APPROVAL"
    })
    return False, "ESCALATE", audit
