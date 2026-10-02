"""looper#39: the voice router's SUBURBS must equal /api/discover's SUBURB_COORDS.

The live map copies web/jarvis/voice-command-router.js; this keeps Looper's
own copy honest so the map has one table to re-sync from. Runs
tools/jarvis-sync-check.js (zero-dep Node), skipped when node is missing.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from routes.discover import SUBURB_COORDS

REPO = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_router_suburbs_match_discover():
    out = subprocess.run(
        [NODE, str(REPO / "tools" / "jarvis-sync-check.js")],
        capture_output=True, text=True, timeout=30,
    )
    assert out.returncode == 0, out.stderr


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_check_reads_every_discover_suburb():
    # Guards the regex parser in the Node tool: it must see all Python rows.
    script = (
        "const s=require(process.argv[1]);"
        "const fs=require('fs');"
        "console.log(Object.keys(s.parseSuburbCoords(fs.readFileSync(process.argv[2],'utf8'))).join('|'))"
    )
    out = subprocess.run(
        [NODE, "-e", script, str(REPO / "tools" / "jarvis-sync-check.js"),
         str(REPO / "backend" / "routes" / "discover.py")],
        capture_output=True, text=True, timeout=30, check=True,
    )
    assert out.stdout.strip().split("|") == list(SUBURB_COORDS)
    assert {"surry hills", "redfern", "alexandria"} <= set(SUBURB_COORDS)
