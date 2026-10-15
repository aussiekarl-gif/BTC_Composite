"""Offline integrity checks for strictly prospective VBTC observations and paper ledger."""
import json
import pandas as pd

import engines.research.forward_paper_200wma as module

def main():
    config,digest=module.config_read()
    dates=pd.date_range("2026-10-05","2026-11-09",freq="W-MON",tz="UTC")
    usd=pd.Series([70000+2000*i for i in range(len(dates))],index=dates,dtype=float)
    ma=pd.Series([50000+100*i for i in range(len(dates))],index=dates,dtype=float)
    market=pd.DataFrame({
        "date":dates,"nav_aud":[20+0.2*i for i in range(len(dates))],
        "last_traded_aud":[20.1+0.2*i for i in range(len(dates))],
        "volume":[50000]*len(dates),
        "premium_pct_calculated":[.5]*len(dates)
    })
    metadata={"sha256":"offline-fake-test-only"}
    original_usd=module.btc_usd_history
    original_issuer=module.download_history
    try:
        module.btc_usd_history=lambda:(usd,ma,dates[-1])
        module.download_history=lambda:(market,metadata)
        now=pd.Timestamp("2026-10-21T02:00:00Z")
        observations,status=module.collect(config,[],now)
        assert status["new_weeks"]==2 and len(observations)==2
        assert observations[0]["bootstrap_only"] is True
        assert observations[-1]["week_end"]=="2026-10-19"
        result=module.simulate_history(observations,config,digest)
        assert result["completed_weeks"]==1
        first=result["weeks"]["2026-10-19"]
        assert len(first["portfolios"])==3
        assert all(first["portfolios"][name]["tax_outstanding_aud"]==0 for name in first["portfolios"])
        extra,status=module.collect(config,observations,pd.Timestamp("2026-10-28T05:00:00Z"))
        assert len(extra)==3 and extra[-1]["week_end"]=="2026-10-26"
        later=module.simulate_history(extra,config,digest)
        assert module.stable(later["weeks"]["2026-10-19"])==module.stable(first)
        # Fail closed rather than invent a retroactive fill weeks later.
        try:
            module.collect(config,observations,pd.Timestamp("2026-11-10T05:00:00Z"))
        except ValueError as exc:
            assert "Missed prospective" in str(exc)
        else:
            raise AssertionError("Retroactive missing paper week was incorrectly allowed")
        # Already captured issuer reference may not be silently repriced.
        edited=market.copy()
        edited.loc[edited["date"]==dates[2],"last_traded_aud"]+=1
        module.download_history=lambda:(edited,metadata)
        try:
            module.collect(config,observations,pd.Timestamp("2026-10-28T05:00:00Z"))
        except ValueError as exc:
            assert "revised" in str(exc)
        else:
            raise AssertionError("Retrospective price revision was incorrectly allowed")
    finally:
        module.btc_usd_history=original_usd
        module.download_history=original_issuer
    print(json.dumps({"paper_forward_integrity":"PASS",
        "first_eligible_week":"2026-10-19",
        "three_simulated_portfolios":"PASS",
        "no_future_lookahead":"PASS",
        "missed_week_fail_closed":"PASS",
        "historical_quote_revision_fail_closed":"PASS"}))

if __name__=="__main__":main()
