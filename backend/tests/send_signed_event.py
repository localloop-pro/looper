"""Manual helper: POST a locally signed BRIDGE-CONTRACT-v1 sample event.

Usage (backend/ as working dir, server running):
    export HYBRIDCARD_INGEST_SECRET=dev-secret     # must match the server
    python tests/send_signed_event.py              # deal.upserted
    python tests/send_signed_event.py --remove     # deal.removed
    python tests/send_signed_event.py --kind card            # card.upserted
    python tests/send_signed_event.py --kind card --remove   # card.removed
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


def build_deal_payload(remove: bool) -> dict:
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


def build_card_payload(remove: bool) -> dict:
    return {
        "event_kind": "card",
        "eventId": str(uuid.uuid4()),
        "hybrid_card_id": "card-demo-1",
        "slug": "bondi-cafe-demo",
        "business_name": "Bondi Cafe (bridge demo)",
        "category": "café",
        "sub_type": "cafe",
        "lat": -33.8908,
        "lng": 151.2748,
        "hours": {"mon-fri": "9-5"},
        "public_card_url": "https://bondi-cafe.hybridcard.ai",
        "archetype": "food",
        "status": "active" if not remove else "unpublished",
        "active": not remove,
        "updated_at": "2026-07-11T00:00:00.000Z",
        "rank_boost": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None,
                        help="default: http://localhost:8000/api/ingest/hybridcard-<kind>")
    parser.add_argument("--kind", choices=("deal", "card"), default="deal")
    parser.add_argument("--remove", action="store_true", help="send active:false (removed event)")
    parser.add_argument("--secret", default=os.environ.get("HYBRIDCARD_INGEST_SECRET", ""))
    parser.add_argument("--key-id", default="hc-1")
    args = parser.parse_args()

    if not args.secret:
        print("Set HYBRIDCARD_INGEST_SECRET (or pass --secret) to match the server.")
        return 1

    url = args.url or f"http://localhost:8000/api/ingest/hybridcard-{args.kind}"
    build = build_deal_payload if args.kind == "deal" else build_card_payload
    raw = json.dumps(build(args.remove)).encode()
    headers = bridge_hmac.sign(raw, args.secret, args.key_id)
    resp = httpx.post(url, content=raw,
                      headers={**headers, "Content-Type": "application/json"})
    print(resp.status_code, resp.text)
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
