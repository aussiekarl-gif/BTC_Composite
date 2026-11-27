"""DNS-over-HTTPS fallback downloader for the public Aethereal CSV.

The original HTTPS hostname is retained and pinned to the resolved IPv4 address
with curl --resolve. curl therefore still performs normal certificate and
hostname verification; insecure TLS flags are deliberately not used.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
from pathlib import Path

import requests

HOST = "dataset.aethereal.top"
CSV_URL = f"https://{HOST}/files/bitcoin-network-daily.csv"
RESOLVERS = (
    (
        "Cloudflare",
        "https://cloudflare-dns.com/dns-query",
        {"accept": "application/dns-json"},
    ),
    (
        "Google",
        "https://dns.google/resolve",
        {"accept": "application/json"},
    ),
)


def extract_ipv4_answer(payload):
    """Return the first valid IPv4 A record, or None for an empty DNS answer."""
    if not isinstance(payload, dict) or payload.get("Status") != 0:
        return None
    for answer in payload.get("Answer") or []:
        if answer.get("type") != 1:
            continue
        try:
            return str(ipaddress.IPv4Address(answer.get("data", "")))
        except ipaddress.AddressValueError:
            continue
    return None


def resolve_aethereal_ipv4(*, get=None, timeout=15):
    """Try Cloudflare then Google DoH; fail explicitly if neither returns A."""
    get = get or requests.get
    failures = []
    for name, endpoint, headers in RESOLVERS:
        try:
            response = get(
                endpoint,
                params={"name": HOST, "type": "A"},
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            address = extract_ipv4_answer(payload)
            if address:
                return name, address
            failures.append(f"{name}: DNS status={payload.get('Status')!r}, no valid A record")
        except (requests.RequestException, ValueError, TypeError) as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    raise RuntimeError("Unable to resolve Aethereal via DoH: " + "; ".join(failures))


def download_csv(output_path, *, get=None, run=None):
    """Resolve via DoH and download using curl with verified HTTPS hostname."""
    run = run or subprocess.run
    resolver, address = resolve_aethereal_ipv4(get=get)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "curl", "--fail", "--location", "--silent", "--show-error",
        "--retry", "2", "--retry-all-errors",
        "--connect-timeout", "15", "--max-time", "60",
        "--resolve", f"{HOST}:443:{address}",
        CSV_URL, "--output", str(output),
    ]
    run(command, check=True, capture_output=True, text=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("Aethereal DoH download produced an empty or missing CSV")
    return {"resolver": resolver, "ipv4": address, "csv": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()
    print(json.dumps(download_csv(args.output_csv), indent=2))


if __name__ == "__main__":
    main()
