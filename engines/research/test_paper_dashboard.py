"""Offline regression tests for GitHub Research VBTC dashboard rendering."""
import json,tempfile
from pathlib import Path
import engines.research.paper_dashboard as dash
import engines.research.forward_paper_200wma as paper

def sample():
    return [
        {"week_end":"2026-10-12","vbtc_trade_reference_aud":20.,
         "vbtc_nav_aud":19.8,"vbtc_premium_pct":1.,
         "btc_usd_close":70000.,"btc_200wma_usd":45000.,
         "btc_deviation_pct":55.5555,"vbtc_market_date":"2026-10-12"},
        {"week_end":"2026-10-19","vbtc_trade_reference_aud":21.,
         "vbtc_nav_aud":20.9,"vbtc_premium_pct":0.4785,
         "btc_usd_close":71000.,"btc_200wma_usd":45100.,
         "btc_deviation_pct":57.42,"vbtc_market_date":"2026-10-19"},
        {"week_end":"2026-10-26","vbtc_trade_reference_aud":22.,
         "vbtc_nav_aud":21.5,"vbtc_premium_pct":2.3256,
         "btc_usd_close":72000.,"btc_200wma_usd":45200.,
         "btc_deviation_pct":59.29,"vbtc_market_date":"2026-10-26"},
    ]

def main():
    config,digest=paper.config_read()
    pending=dash.build(None,config)
    assert "awaiting first completed weekly observation" in pending
    assert "A$500,000.00" in pending
    assert "No forward-test trades" in pending
    assert dash.build(None,config)==pending
    score=paper.simulate_history(sample(),config,digest)
    content=dash.build(score,config)
    assert "2026-10-26" in content and "Simple DCA control" in content
    assert "ETF units" in content and "Net of modelled CGT" in content
    assert "Latest weekly paper fills" in content
    assert content==dash.build(score,config)
    with tempfile.TemporaryDirectory() as temp:
        original=dash.SCORE
        try:
            dash.SCORE=Path(temp)/"test_score.json"
            assert dash.safe_score(digest) is None
            dash.SCORE.write_text(json.dumps(score))
            assert dash.safe_score(digest)["completed_weeks"]==2
            altered={**score,"completed_weeks":5}
            dash.SCORE.write_text(json.dumps(altered))
            try:dash.safe_score(digest)
            except ValueError:pass
            else:raise AssertionError("Inconsistent weeks were accepted")
            altered={**score,"config_sha256":"tampered"}
            dash.SCORE.write_text(json.dumps(altered))
            try:dash.safe_score(digest)
            except ValueError:pass
            else:raise AssertionError("Changed configuration hash was accepted")
        finally:
            dash.SCORE=original
    print(json.dumps({"dashboard_before_first_week":"PASS",
                      "three_portfolio_table":"PASS",
                      "deterministic_history":"PASS",
                      "scorecard_integrity":"PASS"}))

if __name__=="__main__":main()
