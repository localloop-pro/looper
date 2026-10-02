#!/usr/bin/env python3
"""E6 (issue #9) — SLO report and release gate from Looper trace lines.

Reads the JSON lines written by backend/services/correlation.py (`kind:
http` / `kind: bridge`) from a log file or stdin. Other log lines are
skipped, so a raw `docker logs` / Coolify log export works as input.

  report  LOG [--thresholds F] [--out F] [--require-final]
                                            p50/p95/p99 per route, availability,
                                            429s, bridge outcomes and delivery
                                            age; exit 1 if any SLO is breached
  compare BASE.json CAND.json [--thresholds F] [--require-final]
                                            release gate: candidate must beat
                                            the baseline p95 on at least one
                                            target route and regress nowhere;
                                            exit 1 otherwise

--require-final adds a failing check while the thresholds file is still
provisional, so production sign-off can't rest on the placeholder numbers.
An invalid thresholds file exits 2 before anything is measured.

Stdlib only. Reads logs, never the network or a database.
"""
import argparse
import json
import math
import sys
from pathlib import Path

DEFAULT_THRESHOLDS = Path(__file__).with_name("slo_thresholds.json")


def percentile(values, pct):
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def read_records(lines):
    http, bridge = [], []
    for line in lines:
        start = line.find("{")
        if start < 0:
            continue
        try:
            rec = json.loads(line[start:])
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("kind") == "http" and isinstance(rec.get("status"), int):
            http.append(rec)
        elif rec.get("kind") == "bridge" and rec.get("outcome"):
            bridge.append(rec)
    return http, bridge


def summarize(http, bridge):
    routes = {}
    for rec in http:
        routes.setdefault(rec.get("route") or "unmatched", []).append(rec)
    route_stats = {}
    for route, recs in sorted(routes.items()):
        durs = [r["dur_ms"] for r in recs if isinstance(r.get("dur_ms"), (int, float))]
        route_stats[route] = {
            "count": len(recs),
            "p50_ms": percentile(durs, 50),
            "p95_ms": percentile(durs, 95),
            "p99_ms": percentile(durs, 99),
            "error_5xx": sum(1 for r in recs if r["status"] >= 500),
            "rate_limited_429": sum(1 for r in recs if r["status"] == 429),
            "cache_hits": sum(1 for r in recs if r.get("cache") in ("HIT", "STALE")),
        }
    total = len(http)
    errors = sum(1 for r in http if r["status"] >= 500)
    outcomes = {}
    for rec in bridge:
        outcomes[rec["outcome"]] = outcomes.get(rec["outcome"], 0) + 1
    ages = [r["delivery_age_s"] for r in bridge
            if r.get("outcome") == "processed"
            and isinstance(r.get("delivery_age_s"), (int, float))]
    accepted = outcomes.get("processed", 0) + outcomes.get("duplicate", 0) \
        + outcomes.get("stale_skipped", 0)
    stamps = sorted(r["ts"] for r in http + bridge if isinstance(r.get("ts"), str))
    return {
        "window": {
            "first_ts": stamps[0] if stamps else None,
            "last_ts": stamps[-1] if stamps else None,
            "http_requests": total,
            "bridge_events": len(bridge),
        },
        "http": {
            "availability": round(1 - errors / total, 6) if total else None,
            "error_5xx": errors,
            "rate_limited_429": sum(1 for r in http if r["status"] == 429),
            "routes": route_stats,
        },
        "bridge": {
            "outcomes": outcomes,
            # Share of accepted deliveries that were sender retries/replays.
            "duplicate_ratio": round(outcomes.get("duplicate", 0) / accepted, 6)
            if accepted else None,
            "delivery_age_s": {
                "p50": percentile(ages, 50),
                "p95": percentile(ages, 95),
                "max": max(ages) if ages else None,
            },
        },
    }


def _check(name, value, op, limit):
    if value is None:
        return {"slo": name, "value": None, "limit": limit, "ok": False,
                "why": "no data"}
    ok = value >= limit if op == ">=" else value <= limit
    return {"slo": name, "value": value, "op": op, "limit": limit, "ok": ok}


def evaluate(summary, thresholds):
    checks = []
    min_n = thresholds.get("min_samples_per_route", 20)
    checks.append(_check("availability", summary["http"]["availability"], ">=",
                         thresholds["availability_min"]))
    for route, limits in thresholds.get("routes", {}).items():
        stats = summary["http"]["routes"].get(route)
        if not stats or stats["count"] < min_n:
            checks.append({"slo": f"{route} p95_ms", "value": None,
                           "limit": limits["p95_ms_max"], "ok": False,
                           "why": f"fewer than {min_n} samples"})
            continue
        checks.append(_check(f"{route} p95_ms", stats["p95_ms"], "<=",
                             limits["p95_ms_max"]))
    b = thresholds.get("bridge", {})
    if summary["window"]["bridge_events"]:
        bridge = summary["bridge"]
        checks.append(_check("bridge delivery_age p95_s", bridge["delivery_age_s"]["p95"],
                             "<=", b["delivery_age_p95_s_max"]))
        checks.append(_check("bridge duplicate_ratio", bridge["duplicate_ratio"], "<=",
                             b["duplicate_ratio_max"]))
        for outcome in ("unauthorized", "invalid_payload", "too_large"):
            checks.append(_check(f"bridge {outcome}", bridge["outcomes"].get(outcome, 0),
                                 "<=", b.get(f"{outcome}_max", 0)))
    return checks


def compare(base, cand, thresholds):
    rules = thresholds["compare"]
    checks = []
    improved = False
    for route in thresholds.get("routes", {}):
        b = base["http"]["routes"].get(route, {}).get("p95_ms")
        c = cand["http"]["routes"].get(route, {}).get("p95_ms")
        if b is None or c is None:
            checks.append({"slo": f"{route} p95 present in both", "ok": False,
                           "why": "missing route in baseline or candidate"})
            continue
        change_pct = round((b - c) / b * 100, 2) if b else 0.0
        improved = improved or change_pct >= rules["min_p95_improvement_pct"]
        checks.append({"slo": f"{route} p95 no regression", "baseline": b,
                       "candidate": c, "improvement_pct": change_pct,
                       "ok": change_pct >= -rules["max_p95_regression_pct"]})
    checks.append({"slo": "measurable p95 improvement on a target route",
                   "min_pct": rules["min_p95_improvement_pct"], "ok": improved})
    ba, ca = base["http"]["availability"], cand["http"]["availability"]
    checks.append({"slo": "availability no regression", "baseline": ba, "candidate": ca,
                   "ok": ba is not None and ca is not None
                   and ca >= ba - rules["max_availability_drop"]})
    for outcome in ("unauthorized", "invalid_payload"):
        bo = base["bridge"]["outcomes"].get(outcome, 0)
        co = cand["bridge"]["outcomes"].get(outcome, 0)
        checks.append({"slo": f"bridge {outcome} no increase", "baseline": bo,
                       "candidate": co, "ok": co <= bo})
    return checks


def _is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def threshold_problems(t):
    """Everything wrong with a thresholds file; [] means usable."""
    problems = []

    def need(where, key, low=0, high=None, positive=False):
        value = where.get(key) if isinstance(where, dict) else None
        if not _is_num(value):
            problems.append(f"{key}: missing or not a number")
        elif value < low or (positive and value <= 0) or (high is not None and value > high):
            problems.append(f"{key}: {value} is out of range")

    if not isinstance(t.get("provisional"), bool):
        problems.append("provisional: must be true or false")
    elif not t["provisional"] and not (isinstance(t.get("adr"), str) and t["adr"].strip()):
        problems.append("adr: final thresholds must name the E1 ADR they came from")
    need(t, "availability_min", high=1, positive=True)
    need(t, "min_samples_per_route", positive=True)
    routes = t.get("routes")
    if not isinstance(routes, dict) or not routes:
        problems.append("routes: at least one target route is required")
    else:
        for route, limits in routes.items():
            if not (isinstance(limits, dict) and _is_num(limits.get("p95_ms_max"))
                    and limits["p95_ms_max"] > 0):
                problems.append(f"{route} p95_ms_max: must be a positive number")
    bridge = t.get("bridge", {})
    need(bridge, "delivery_age_p95_s_max", positive=True)
    need(bridge, "duplicate_ratio_max", high=1)
    for key in ("unauthorized_max", "invalid_payload_max", "too_large_max"):
        need(bridge, key)
    rules = t.get("compare", {})
    for key in ("min_p95_improvement_pct", "max_p95_regression_pct",
                "max_availability_drop"):
        need(rules, key)
    return problems


def _final_check(thresholds):
    ok = thresholds.get("provisional") is False
    check = {"slo": "thresholds final (E1 ADR)", "ok": ok, "adr": thresholds.get("adr")}
    if not ok:
        check["why"] = "slo_thresholds.json is provisional (localloop.pro-main#100)"
    return check


def _load_json(path):
    return json.loads(Path(path).read_text())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rep = sub.add_parser("report")
    rep.add_argument("log", help="trace log file, or - for stdin")
    rep.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS))
    rep.add_argument("--out", help="also write the report JSON here")
    rep.add_argument("--require-final", action="store_true",
                     help="fail while the thresholds are provisional (production sign-off)")
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("baseline")
    cmp_.add_argument("candidate")
    cmp_.add_argument("--thresholds", default=str(DEFAULT_THRESHOLDS))
    cmp_.add_argument("--require-final", action="store_true",
                      help="fail while the thresholds are provisional (production sign-off)")
    args = ap.parse_args(argv)
    thresholds = _load_json(args.thresholds)
    problems = threshold_problems(thresholds)
    if problems:
        print(f"invalid thresholds file {args.thresholds}:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    if args.cmd == "report":
        if args.log == "-":
            lines = sys.stdin.read().splitlines()
        else:
            lines = Path(args.log).read_text(errors="replace").splitlines()
        summary = summarize(*read_records(lines))
        checks = evaluate(summary, thresholds)
        if args.require_final:
            checks.append(_final_check(thresholds))
        result = {**summary, "slo": checks, "pass": all(c["ok"] for c in checks),
                  "thresholds_provisional": thresholds.get("provisional", False)}
        text = json.dumps(result, indent=2, sort_keys=True)
        if args.out:
            Path(args.out).write_text(text + "\n")
        print(text)
        return 0 if result["pass"] else 1

    checks = compare(_load_json(args.baseline), _load_json(args.candidate), thresholds)
    if args.require_final:
        checks.append(_final_check(thresholds))
    result = {"gate": checks, "pass": all(c["ok"] for c in checks),
              "thresholds_provisional": thresholds.get("provisional", False)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
