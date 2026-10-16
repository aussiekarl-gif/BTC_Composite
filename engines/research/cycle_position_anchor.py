"""Reconcile the ORIGINAL per-asset inventory available on halving day500.

Historical exit % uses *original* BTC positions before day500, not
total lifetime purchases or shares acquired later. The FIFO assumption
in the user's executed ledger means sales during the distribution window
dispose of original pre-day500 holdings before new ones bought later.

Fail CLOSED for missing or invalid records; do not estimate an original
2025 IBIT/BTC position for the user's actual 2026-deployment portfolio.
No tax lots or real broker confirmation are established here.
"""
from __future__ import annotations

import math
import pandas as pd

from engines.shared.portfolio_transactions import (
    parse_date,portfolio_positions,
)

ASSETS=("ASX:IBIT","Direct BTC")


def original_cycle_inventory(saved,halving,*,asof):
    portfolio_positions(saved)  # fail on invalid / oversold transactions
    day500=(pd.Timestamp(halving)+pd.Timedelta(days=500)).date()
    end=pd.Timestamp(asof).date()
    if end<day500:
        return {"eligible":False,"day500":str(day500),
                "reason":"Day500 has not occurred; original position not yet fixed."}
    buys=saved.get("rows",[])
    sells=saved.get("sales",[])
    anchored={a:0. for a in ASSETS}
    pre_sale={a:0. for a in ASSETS}
    post_sale={a:0. for a in ASSETS}
    for entry in buys:
        asset=entry["Asset"]
        if asset not in ASSETS:raise ValueError("Unknown BUY asset")
        date=parse_date(entry["Date"])
        if date<day500:
            anchored[asset]+=float(entry["Units / BTC Received"])
    for entry in sells:
        asset=entry["Asset"]
        if asset not in ASSETS:raise ValueError("Unknown SELL asset")
        date=parse_date(entry["Date"])
        qty=float(entry["Units Sold"])
        if date<day500:
            pre_sale[asset]+=qty
        elif date<=end:
            post_sale[asset]+=qty
    original={a:max(0.,anchored[a]-pre_sale[a]) for a in ASSETS}
    sold_original={a:min(original[a],post_sale[a]) for a in ASSETS}
    remaining={a:max(0.,original[a]-sold_original[a]) for a in ASSETS}
    # An account funded after the first SELL review cannot fabricate
    # earlier distribution through retrospective holding assumptions.
    return {
        "eligible":any(v>1e-8 for v in original.values()),
        "day500":str(day500),
        "asof":str(end),
        "original_holdings":original,
        "sold_from_original":sold_original,
        "remaining_original":remaining,
        "original_sold_fraction":{
            a:(sold_original[a]/original[a] if original[a]>1e-8 else None)
            for a in ASSETS
        },
        "reason":(
            "Pre-day500 executed holdings reconciled from saved BUY/SELL ledger."
            if any(v>1e-8 for v in original.values())
            else "No pre-day500 holdings: cannot apply legacy cycle SELL fractions "
                 "to positions acquired after day500."
        ),
        "account_source":"Recorded BUY/SELL rows only; broker verification required",
    }
