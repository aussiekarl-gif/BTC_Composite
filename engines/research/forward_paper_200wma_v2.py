"""Research-only v2 prospective UTC weekly observation gate. No network or live writes."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path("research_forward/200wma_v2")
CONFIG = ROOT / "config_frozen.json"
EVENTS = ROOT / "weekly_observations.jsonl"

def parse_utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must explicitly be UTC")
    return dt.astimezone(timezone.utc)

def last_completed_monday(now):
    now = parse_utc(now) if isinstance(now, str) else now
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("UTC now required")
    monday = now.date() - timedelta(days=now.weekday())
    if now.weekday() == 0:
        monday -= timedelta(days=7)
    return monday.isoformat()

def load_config():
    data = json.loads(CONFIG.read_text())
    if data.get("schema") != "btc-200wma-paper-v2":
        raise ValueError("Wrong research schema")
    return data, hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def validate_observation(row, config, now):
    """Validate a prospective record before any future collector can append it."""
    today = parse_utc(now)
    week = datetime.fromisoformat(row["week_end"]).date()
    if week.weekday() != 0 or week.isoformat() > last_completed_monday(today):
        raise ValueError("Incomplete or non-Monday week")
    if week < datetime.fromisoformat(config["earliest_first_completed_week_utc"]).date():
        raise ValueError("Week predates v2 inception")
    observed = parse_utc(row["observed_at_utc"])
    if observed > today or observed.date() < week or (observed.date() - week).days > 7:
        raise ValueError("Missing, future or retroactive capture")
    source = parse_utc(row["btc_source_at_utc"])
    if source > observed or source.date() < week:
        raise ValueError("Stale or future BTC source")
    issuer_date = datetime.fromisoformat(row["vbtc_market_date"]).date()
    if issuer_date > observed.date() or (week - issuer_date).days not in range(4):
        raise ValueError("Stale or future VBTC quote")
    for field in ("btc_usd_close", "btc_200wma_usd", "vbtc_trade_reference_aud"):
        value = float(row[field])
        if not 0 < value < float("inf"):
            raise ValueError("Invalid price")
    if len(row["vbtc_issuer_workbook_sha256"]) != 64:
        raise ValueError("Missing issuer workbook digest")
    return True

def validate_append(existing, candidate, config, now):
    validate_observation(candidate, config, now)
    if existing:
        last = datetime.fromisoformat(existing[-1]["week_end"]).date()
        current = datetime.fromisoformat(candidate["week_end"]).date()
        if current != last + timedelta(days=7):
            raise ValueError("Duplicate or missing week")
    return True

def main():
    config, digest = load_config()
    print(json.dumps({"status": "v2_validation_only", "config_sha256": digest,
                      "latest_completed_week": last_completed_monday(datetime.now(timezone.utc).isoformat()),
                      "live_writes": False}))

if __name__ == "__main__":
    main()
