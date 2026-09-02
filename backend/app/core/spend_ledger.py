_LEDGER: dict[str, float] = {}


def get_spent_today(mandate_id: str) -> float:
    return _LEDGER.get(mandate_id, 0.0)


def record_spend(mandate_id: str, amount: float) -> float:
    _LEDGER[mandate_id] = _LEDGER.get(mandate_id, 0.0) + amount
    return _LEDGER[mandate_id]
