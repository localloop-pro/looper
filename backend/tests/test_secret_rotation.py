"""Bridge secret rotation guards (looper#48).

A real HYBRIDCARD_INGEST_SECRET value sits in public git history, so the
owner must rotate it (docs/SECRET-ROTATION.md). These tests pin down what a
rotation actually does on the receiver side, and stop a new value from
being committed to the tree.
"""
import json
import pathlib
import re
import subprocess

import pytest

from services import bridge_hmac

REPO = pathlib.Path(__file__).resolve().parents[2]
BODY = json.dumps({"eventId": "rot-1", "type": "deal.upserted"}).encode()


def _signed(secret, key_id="hc-1"):
    # verify() reads headers case-insensitively (Starlette); a plain dict
    # needs the lowercase names
    return {k.lower(): v for k, v in bridge_hmac.sign(BODY, secret, key_id).items()}


def test_rotated_secret_rejects_old_signatures(monkeypatch):
    """After the env swap + restart, the old secret no longer verifies."""
    monkeypatch.setenv("HYBRIDCARD_INGEST_SECRET", "new-rotated-value")
    with pytest.raises(bridge_hmac.BridgeAuthError, match="signature mismatch"):
        bridge_hmac.verify(BODY, _signed("old-leaked-value"))
    assert bridge_hmac.verify(BODY, _signed("new-rotated-value")) == "hc-1"


def test_new_key_id_alone_does_not_rotate(monkeypatch):
    """Adding hc-2 to HYBRIDCARD_KEY_IDS shares the SAME secret, so it
    retires nothing: the old secret still verifies under hc-2. Rotation
    means changing HYBRIDCARD_INGEST_SECRET itself (see the runbook)."""
    monkeypatch.setenv("HYBRIDCARD_INGEST_SECRET", "same-value")
    monkeypatch.setenv("HYBRIDCARD_KEY_IDS", "hc-2")
    assert bridge_hmac.verify(BODY, _signed("same-value", "hc-2")) == "hc-2"


def test_empty_secret_accepts_nothing(monkeypatch):
    """A blanked secret (e.g. mid-rotation) must fail closed, not open."""
    monkeypatch.setenv("HYBRIDCARD_INGEST_SECRET", "")
    assert bridge_hmac.load_keys() == {}
    with pytest.raises(bridge_hmac.BridgeAuthError, match="unknown key id"):
        bridge_hmac.verify(BODY, _signed(""))


# A long hex (openssl rand -hex) or base64 run assigned to a bridge secret
# name. Placeholders such as "<openssl rand -hex 32>",
# "replace-with-openssl-rand-hex-32", "test-secret" or "$(cat …)" don't match.
SECRET_ASSIGN = re.compile(
    r"(HYBRIDCARD_INGEST_SECRET|LOCALLOOP_BRIDGE_SECRET)[\"']?\s*[:=]\s*[\"']?"
    r"(?:[0-9a-fA-F]{32,}|[A-Za-z0-9+/]{40,}={0,2})"
)


def test_no_bridge_secret_values_in_tracked_files():
    files = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True
    ).stdout.decode().split("\0")
    hits = []
    for rel in filter(None, files):
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if SECRET_ASSIGN.search(line):
                hits.append(f"{rel}:{n}")  # location only, never the value
    assert not hits, f"bridge secret value committed at: {hits}"


@pytest.mark.parametrize("path", ["/api/ingest/hybridcard-deal", "/api/ingest/hybridcard-card"])
def test_empty_body_probe_writes_nothing(client, db, path):
    """The runbook's live check: a signed `{}` gets 422 when the secret
    matches and 401 when it doesn't, and writes nothing either way."""
    from tests.conftest import signed_post
    from models import BridgeEvent

    assert signed_post(client, path, {}).status_code == 422
    assert signed_post(client, path, {}, secret="old-leaked-value").status_code == 401
    assert db.query(BridgeEvent).count() == 0
