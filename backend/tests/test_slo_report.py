"""E6 (issue #9) — tools/slo_report.py and the e6_nonprod_check target guard."""
import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import e6_nonprod_check  # noqa: E402
import slo_report  # noqa: E402

THRESHOLDS = json.loads((TOOLS / "slo_thresholds.json").read_text())


def _http(route, dur, status=200, cache=None):
    return json.dumps({"kind": "http", "route": route, "dur_ms": dur, "status": status,
                       "cache": cache, "rid": "x" * 32, "method": "GET",
                       "ts": "2026-10-02T00:00:00.000+00:00"})


def _bridge(outcome, age=5.0):
    return json.dumps({"kind": "bridge", "outcome": outcome, "delivery_age_s": age,
                       "receiver": "hybridcard-deal", "event_id": "e", "rid": "r",
                       "event_type": "deal.upserted",
                       "ts": "2026-10-02T00:00:01.000+00:00"})


def _lines(dur=10.0, n=40, errors=0, bridge=()):
    lines = ["INFO:     Uvicorn running on http://0.0.0.0:8010", "not json {broken"]
    for route in THRESHOLDS["routes"]:
        lines += [_http(route, dur + i * 0.1) for i in range(n)]
    lines += [_http("/api/search", 5, status=500) for _ in range(errors)]
    lines += list(bridge)
    return lines


def test_percentile_nearest_rank():
    assert slo_report.percentile([], 95) is None
    assert slo_report.percentile(list(range(1, 101)), 95) == 95
    assert slo_report.percentile([7], 50) == 7


def test_report_skips_noise_and_passes_healthy_window():
    summary = slo_report.summarize(*slo_report.read_records(
        _lines(bridge=[_bridge("processed"), _bridge("duplicate")])))
    assert summary["window"]["http_requests"] == 120
    assert summary["http"]["availability"] == 1.0
    assert summary["bridge"]["duplicate_ratio"] == 0.5
    checks = slo_report.evaluate(summary, THRESHOLDS)
    failing = {c["slo"] for c in checks if not c["ok"]}
    assert failing == {"bridge duplicate_ratio"}  # 0.5 > 0.25


def test_report_fails_on_latency_errors_and_bridge_auth():
    lines = _lines(dur=400.0, errors=5,
                   bridge=[_bridge("processed", age=3600), _bridge("unauthorized", None)])
    checks = slo_report.evaluate(slo_report.summarize(*slo_report.read_records(lines)),
                                 THRESHOLDS)
    failing = {c["slo"] for c in checks if not c["ok"]}
    assert {"availability", "/api/search p95_ms", "bridge delivery_age p95_s",
            "bridge unauthorized"} <= failing


def test_too_few_samples_is_a_failure_not_a_pass():
    checks = slo_report.evaluate(
        slo_report.summarize(*slo_report.read_records(_lines(n=3))), THRESHOLDS)
    assert not any(c["ok"] for c in checks if c["slo"].endswith("p95_ms"))


def test_compare_requires_improvement_and_no_regression():
    base = slo_report.summarize(*slo_report.read_records(_lines(dur=100.0)))
    faster = slo_report.summarize(*slo_report.read_records(_lines(dur=50.0)))
    same = slo_report.summarize(*slo_report.read_records(_lines(dur=100.0)))
    slower = slo_report.summarize(*slo_report.read_records(_lines(dur=150.0)))
    assert all(c["ok"] for c in slo_report.compare(base, faster, THRESHOLDS))
    assert not all(c["ok"] for c in slo_report.compare(base, same, THRESHOLDS))
    assert not all(c["ok"] for c in slo_report.compare(base, slower, THRESHOLDS))


def test_cli_exit_codes(tmp_path):
    log = tmp_path / "trace.log"
    log.write_text("\n".join(_lines()))
    out = tmp_path / "r.json"
    assert slo_report.main(["report", str(log), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["pass"] is True
    log.write_text("\n".join(_lines(dur=900.0)))
    assert slo_report.main(["report", str(log)]) == 1


@pytest.mark.parametrize("url", [
    "https://api.localloop.ai", "https://looper.localloop.ai", "https://localloop.ai",
    "https://hybridcard.ai", "http://looper-api.167.86.79.151.sslip.io",
    "https://www.localloop.pro",
])
def test_nonprod_check_refuses_production(url):
    with pytest.raises(SystemExit):
        e6_nonprod_check.guard_target(url, url.split("//")[1])


def test_nonprod_check_needs_explicit_opt_in_for_remote_hosts():
    e6_nonprod_check.guard_target("http://127.0.0.1:8010", None)
    with pytest.raises(SystemExit):
        e6_nonprod_check.guard_target("http://staging.example:8010", None)
    e6_nonprod_check.guard_target("http://staging.example:8010", "staging.example")


# --- looper#20: provisional thresholds can never sign off a production release ---

def test_shipped_thresholds_are_valid_and_still_provisional():
    # Flip this assert in the same PR that pastes in the E1 ADR numbers.
    assert slo_report.threshold_problems(THRESHOLDS) == []
    assert THRESHOLDS["provisional"] is True
    assert THRESHOLDS["adr"] is None


@pytest.mark.parametrize("mutate, problem", [
    (lambda t: t.pop("availability_min"), "availability_min"),
    (lambda t: t.update(availability_min=1.5), "availability_min"),
    (lambda t: t["routes"]["/api/search"].update(p95_ms_max=-1), "/api/search"),
    (lambda t: t["routes"].clear(), "routes"),
    (lambda t: t["bridge"].update(unauthorized_max="0"), "unauthorized_max"),
    (lambda t: t["compare"].pop("min_p95_improvement_pct"), "min_p95_improvement_pct"),
    (lambda t: t.update(provisional=False), "adr"),
    (lambda t: t.pop("provisional"), "provisional"),
])
def test_bad_threshold_files_are_rejected(mutate, problem):
    bad = json.loads(json.dumps(THRESHOLDS))
    mutate(bad)
    problems = slo_report.threshold_problems(bad)
    assert any(problem in p for p in problems), problems


def test_final_thresholds_need_an_adr_reference():
    final = json.loads(json.dumps(THRESHOLDS))
    final.update(provisional=False, adr="localloop-pro/localloop.pro-main#100")
    assert slo_report.threshold_problems(final) == []


def test_require_final_fails_a_green_window_on_provisional_numbers(tmp_path):
    log = tmp_path / "trace.log"
    log.write_text("\n".join(_lines()))
    out = tmp_path / "r.json"
    assert slo_report.main(["report", str(log), "--out", str(out)]) == 0
    assert slo_report.main(["report", str(log), "--require-final", "--out", str(out)]) == 1
    result = json.loads(out.read_text())
    assert result["thresholds_provisional"] is True
    assert [c["slo"] for c in result["slo"] if not c["ok"]] == ["thresholds final (E1 ADR)"]

    final = json.loads(json.dumps(THRESHOLDS))
    final.update(provisional=False, adr="localloop-pro/localloop.pro-main#100")
    tfile = tmp_path / "final.json"
    tfile.write_text(json.dumps(final))
    assert slo_report.main(["report", str(log), "--require-final",
                            "--thresholds", str(tfile)]) == 0


def test_require_final_applies_to_compare(tmp_path):
    base = tmp_path / "base.json"
    cand = tmp_path / "cand.json"
    base.write_text(json.dumps(slo_report.summarize(*slo_report.read_records(_lines(dur=100.0)))))
    cand.write_text(json.dumps(slo_report.summarize(*slo_report.read_records(_lines(dur=50.0)))))
    assert slo_report.main(["compare", str(base), str(cand)]) == 0
    assert slo_report.main(["compare", str(base), str(cand), "--require-final"]) == 1


def test_invalid_threshold_file_exits_2(tmp_path, capsys):
    bad = json.loads(json.dumps(THRESHOLDS))
    bad["routes"]["/api/search"]["p95_ms_max"] = 0
    tfile = tmp_path / "bad.json"
    tfile.write_text(json.dumps(bad))
    log = tmp_path / "trace.log"
    log.write_text("\n".join(_lines()))
    assert slo_report.main(["report", str(log), "--thresholds", str(tfile)]) == 2
    assert "/api/search" in capsys.readouterr().err
