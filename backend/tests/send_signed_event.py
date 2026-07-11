"""Manual helper: POST a locally signed BRIDGE-CONTRACT-v1 sample event.

Usage (backend/ as working dir, server running):
    export HYBRIDCARD_INGEST_SECRET=dev-secret     # must match the server
    python tests/send_signed_event.py              # deal.upserted
    python tests/send_signed_event.py --remove     # deal.removed
"""
import argparse
import json
import os
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import httpx

from services import bridge_hmac


def build_payload(remove: bool) -> dict:
    return {
        "source": "hybridcard",
        "eventId": str(uuid.uuid4()),
        "hybrid_card_id": "card-demo-1",
        "deal_id": "deal-demo-1",
        "business_name": "Bondi Cafe (bridge demo)",
        "category": "café",
        "pin_type": "offering",
        "sub_type": "cafe",
        "title": "30% off lunch",
        "short_description": "Bridge demo deal",
        "discount_size": 30,
        "lat": -33.8908,
        "lng": 151.2748,
        "hours": "9-5",
        "public_card_url": "https://bondi-cafe.hybridcard.ai",
        "active": not remove,
        "updated_at": "2026-07-11T00:00:00.000Z",
        "rank_boost": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000/api/ingest/hybridcard-deal")
    parser.add_argument("--remove", action="store_true", help="send active:false (deal.removed)")
    parser.add_argument("--secret", default=os.environ.get("HYBRIDCARD_INGEST_SECRET", ""))
    parser.add_argument("--key-id", default="hc-1")
    args = parser.parse_args()

    if not args.secret:
        print("Set HYBRIDCARD_INGEST_SECRET (or pass --secret) to match the server.")
        return 1

    raw = json.dumps(build_payload(args.remove)).encode()
    headers = bridge_hmac.sign(raw, args.secret, args.key_id)
    resp = httpx.post(args.url, content=raw,
                      headers={**headers, "Content-Type": "application/json"})
    print(resp.status_code, resp.text)
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
