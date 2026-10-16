"""Illustrative 25% vs 40% execution-price error sensitivity; research only.

Run as python -m engines.research.price_error_sensitivity --output <path>.
These are ex-post price-error assumptions, not a causal DCA backtest.
"""
import argparse
import json
from pathlib import Path
from engines.research.diminishing_cycle_smsf_projection import SCENARIOS, model

def compare():
    return {
        "not_forecast": True,
        "price_error_definition": "Sell at 75%/60% of future peak and rebuy at 125%/140% of future trough",
        "errors": {
            str(int(e*100))+"pct": {name: model(case,top_error=e,bottom_error=e)
                for name,case in SCENARIOS.items()}
            for e in (.25,.40)
        },
        "warnings": [
            "Full peak/trough knowledge is not possible; results do not validate dynamic DCA",
            "Each 16-order leg executes at one hypothetical price, not weekly observations",
            "10% SMSF tax is an assumed effective rate on eligible long-term realised gains",
        ]
    }

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="")
    args=parser.parse_args()
    result=json.dumps(compare(),indent=2)
    if args.output: Path(args.output).write_text(result+"\n",encoding="utf-8")
    print(result)
