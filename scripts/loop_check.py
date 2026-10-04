#!/usr/bin/env python3
"""Owner-run loop readiness probe. Sends only GET/HEAD; never follows redirects."""

import argparse
import json
import math
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, method):
    """Return status/body without credentials, cookies, redirects or retries."""
    if method not in ("GET", "HEAD"):
        raise ValueError("Only GET and HEAD are permitted")
    req = Request(url, method=method, headers={"User-Agent": "Looper-loop-check/1"})
    try:
        with build_opener(NoRedirects()).open(req, timeout=10) as response:
            body = response.read(2_000_001) if method == "GET" else b""
            if len(body) > 2_000_000:
                raise ValueError("response exceeds 2 MB")
            return response.status, body
    except HTTPError as error:
        with error:
            return error.code, b""


def safe_card_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        return (parsed.scheme == "https" and
                (host == "hybridcard.ai" or host.endswith(".hybridcard.ai")) and
                parsed.username is None and parsed.password is None and
                parsed.port in (None, 443) and "\\" not in value)
    except ValueError:
        return False


def one_line(value):
    # Untrusted business labels cannot forge PASS lines or terminal escapes.
    return json.dumps(str(value), ensure_ascii=True)


def health_commit(body):
    """Commit from /health (looper#86); "unknown" unless it is a short hex sha."""
    try:
        commit = json.loads(body).get("commit")
    except (ValueError, UnicodeError, RecursionError, AttributeError):
        return "unknown"
    if (isinstance(commit, str) and 0 < len(commit) <= 40 and
            all(c in "0123456789abcdef" for c in commit)):
        return commit
    return "unknown"


def check(args):
    checks = []

    def report(ok, label, detail):
        checks.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {label}: {detail}")

    def probe(url, method="GET"):
        try:
            return request(url, method)
        except (OSError, URLError, HTTPException, ValueError):
            # Do not print response bodies or network errors that may contain data.
            return None, b""

    base = args.base_url.rstrip("/")
    status, body = probe(base + "/health")
    report(status == 200, "health", f"HTTP {status or 'unavailable'} (expected 200); "
           f"commit {health_commit(body) if status == 200 else 'unknown'}")
    for path in ("/api/users/1", "/api/code/ABC123"):
        status, _ = probe(base + path)
        report(status in (403, 404, 405), path,
               f"HTTP {status or 'unavailable'} (expected 403/404/405)")

    query = urlencode({"q": args.query, "lat": args.lat, "lng": args.lng,
                       "radius_km": args.radius_km})
    status, body = probe(base + "/api/search?" + query)
    results = None
    if status == 200:
        try:
            data = json.loads(body)
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                results = data["results"]
        except (ValueError, UnicodeError, RecursionError):
            pass
    report(results is not None and len(results) >= 2, "search",
           f"{len(results)} results (expected at least 2)" if results is not None
           else f"HTTP {status or 'unavailable'}; missing/invalid results")
    if not results:
        report(False, "card URLs", "no results to validate")
        report(False, "card HEAD", "no cards to probe")
    for index, result in enumerate(results or [], 1):
        result = result if isinstance(result, dict) else {}
        name = one_line(result.get("name") or f"result {index}")
        url = result.get("card_url")
        valid = safe_card_url(url)
        report(valid, f"card URL {name}", one_line(url))
        if valid:
            status, _ = probe(url, "HEAD")
            report(status is not None and 200 <= status < 400,
                   f"card HEAD {name}", f"HTTP {status or 'unavailable'}")
        else:
            report(False, f"card HEAD {name}", "skipped unsafe/missing card URL")
    ready = all(checks)
    print("READY" if ready else "NOT READY")
    return 0 if ready else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--lat", type=float, default=-33.8908)
    parser.add_argument("--lng", type=float, default=151.2748)
    parser.add_argument("--radius-km", type=float, default=1.5)
    parser.add_argument("--query", default="hairdresser")
    args = parser.parse_args(argv)
    try:
        base = urlsplit(args.base_url)
        valid = (base.scheme in ("http", "https") and base.hostname and
                 base.username is None and base.password is None and
                 not base.query and not base.fragment and base.path in ("", "/") and
                 base.port != 0 and "\\" not in args.base_url and
                 not any(c.isspace() or ord(c) < 32 for c in args.base_url))
    except ValueError:
        valid = False
    if not valid:
        parser.error("--base-url must be an HTTP(S) origin without credentials/query/fragment")
    if not (-90 <= args.lat <= 90 and -180 <= args.lng <= 180 and
            math.isfinite(args.radius_km) and args.radius_km > 0):
        parser.error("coordinates must be in range and radius-km finite and positive")
    return check(args)


if __name__ == "__main__":
    raise SystemExit(main())
