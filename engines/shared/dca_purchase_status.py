"""Consistent display state for DCA Today purchase recommendations."""

def dca_purchase_display(
    *,
    portfolio_verified: bool,
    risk_multiplier: float,
    effective_multiplier: float,
    recommended_buy_aud: float,
    base_allowance_aud: float,
    remaining_capital_aud: float,
    portfolio_verification_reason: str | None = None,
) -> dict:
    """Return one coherent status for the hero, reason and cash labels."""
    if not portfolio_verified:
        return {
            "amount": "BLOCKED",
            "pill": "PORTFOLIO NOT VERIFIED",
            "pill_class": "blocked",
            "sub": "Cash sizing withheld",
            "allowance": "Unavailable",
            "remaining": "Unavailable",
            "reason_title": "Cash sizing blocked",
            "reason_sub": (portfolio_verification_reason or "Authoritative portfolio could not be verified; no purchase amount is available."),
        }

    allowance = f"A$ {float(base_allowance_aud):,.0f}"
    remaining = f"A$ {float(remaining_capital_aud):,.0f}"
    if float(risk_multiplier) <= 0.0:
        return {
            "amount": "A$ 0",
            "pill": "NO BUY THIS WEEK",
            "pill_class": "blocked",
            "sub": "Risk score is in the 0.40+ no-buy band",
            "allowance": allowance,
            "remaining": remaining,
            "reason_title": "Risk policy: NO BUY",
            "reason_sub": "Risk score is 0.40 or higher; the selected ladder sets the multiplier to 0×.",
        }

    if float(recommended_buy_aud) <= 0.0:
        return {
            "amount": "A$ 0",
            "pill": "NO BUY — NO DEPLOYABLE CASH",
            "pill_class": "blocked",
            "sub": "No deployable cash is available",
            "allowance": allowance,
            "remaining": remaining,
            "reason_title": "No deployable cash",
            "reason_sub": "The verified portfolio has no cash available for a purchase.",
        }

    return {
        "amount": f"A$ {float(recommended_buy_aud):,.0f}",
        "pill": "BUY THIS WEEK",
        "pill_class": "ready",
        "sub": f"That's {float(effective_multiplier):.2f}× the base weekly allowance",
        "allowance": allowance,
        "remaining": remaining,
        "reason_title": "Risk policy: BUY BAND",
        "reason_sub": "Portfolio verified, deployable cash available, and risk is below the 0.40 no-buy threshold.",
    }
