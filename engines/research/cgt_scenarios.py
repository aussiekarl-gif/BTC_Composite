"""Research-only Australian CGT scenario calculations; not tax advice.

Assumes Australian resident individual, 12-month CGT discount eligibility,
a flat illustrative marginal tax rate, no other gains/losses or Medicare effects.
Not suitable for SMSFs, companies, tax returns or actual tax estimates.
"""


def illustrative_cgt_on_gain(realized_gain_aud, holding_days, marginal_rate=0.45,
                             discount=0.50):
    """Return tax on a *gain*, not sale proceeds, using an illustrative discount.

    Negative realized gains generate no immediate tax credit; losses require
    separate carry-forward tracking in a complete portfolio tax model.
    """
    gain = float(realized_gain_aud)
    days = int(holding_days)
    rate = float(marginal_rate)
    reduction = float(discount)
    if not 0 <= rate <= 1 or not 0 <= reduction <= 1 or days < 0:
        raise ValueError("Invalid CGT scenario parameters")
    taxable = max(0.0, gain) * (1 - reduction if days >= 365 else 1)
    return taxable * rate


def illustrative_after_tax_sale(gross_proceeds_aud, cost_basis_aud,
                                holding_days, fee_aud=0.0,
                                marginal_rate=0.45, discount=0.50):
    """Illustrative net sale cash after fees and CGT on net capital gain."""
    gross = float(gross_proceeds_aud)
    basis = float(cost_basis_aud)
    fee = float(fee_aud)
    if min(gross, basis, fee) < 0 or fee > gross:
        raise ValueError("Invalid sale proceeds, basis or fee")
    gain = gross - fee - basis
    tax = illustrative_cgt_on_gain(gain, holding_days, marginal_rate, discount)
    return {"realized_gain_aud": gain, "illustrative_cgt_aud": tax,
            "reinvestment_cash_aud": gross - fee - tax}
