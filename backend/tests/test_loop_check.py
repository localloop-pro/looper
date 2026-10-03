"""Issue #75: local TestClient only; every card HEAD is stubbed (no live DNS)."""
import importlib.util
from pathlib import Path
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "loop_check.py"
spec = importlib.util.spec_from_file_location("loop_check", SCRIPT)
loop_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop_check)


@pytest.fixture
def target(monkeypatch):
    state = {
        "results": [
            {"name": "Bondi Salon", "card_url": "https://salon.hybridcard.ai"},
            {"name": "Bondi Barber", "card_url": "https://hybridcard.ai/c/barber"},
        ],
        "health": 200, "users": 404, "code": 404, "head": 200,
        "calls": [],
    }
    app = FastAPI()

    @app.get("/health")
    def health():
        return JSONResponse({}, status_code=state["health"])

    @app.get("/api/users/1")
    def users():
        return JSONResponse({"name": "private-profile-must-not-print"},
                            status_code=state["users"])

    @app.get("/api/code/ABC123")
    def code():
        return JSONResponse({}, status_code=state["code"])

    @app.get("/api/search")
    def search(request: Request):
        state["query"] = dict(request.query_params)
        return state.get("payload", {"results": state["results"]})

    with TestClient(app) as client:
        def stub(url, method):
            state["calls"].append((url, method))
            if urlsplit(url).hostname == "testserver":
                assert method == "GET"
                response = client.get(url, follow_redirects=False)
                return response.status_code, response.content
            assert method == "HEAD"
            assert loop_check.safe_card_url(url)
            if state["head"] == "timeout":
                raise TimeoutError()
            return state["head"], b""
        monkeypatch.setattr(loop_check, "request", stub)
        yield state


def run(capsys, *args):
    status = loop_check.main(["--base-url", "http://testserver", *args])
    return status, capsys.readouterr().out


def test_all_pass_and_dock_defaults(target, capsys):
    status, output = run(capsys)
    assert status == 0 and output.splitlines()[-1] == "READY"
    assert len(output.splitlines()) == 9
    assert all(line.startswith("PASS ") for line in output.splitlines()[:-1])
    assert target["query"] == {"q": "hairdresser", "lat": "-33.8908",
                               "lng": "151.2748", "radius_km": "1.5"}
    assert [method for _, method in target["calls"]] == ["GET"] * 4 + ["HEAD"] * 2


def test_localhost_card_names_business_and_never_fetches_it(target, capsys):
    target["results"][0]["card_url"] = "http://localhost:3000/c/salon"
    status, output = run(capsys)
    assert status == 1
    assert 'FAIL card URL "Bondi Salon": "http://localhost:3000/c/salon"' in output
    assert all("localhost" not in url for url, _ in target["calls"])
    assert output.splitlines()[-1] == "NOT READY"


def test_one_result_fails(target, capsys):
    target["results"].pop()
    status, output = run(capsys)
    assert status == 1 and "FAIL search: 1 results" in output


@pytest.mark.parametrize("head", [404, 500, "timeout"])
def test_card_head_failure(target, capsys, head):
    target["head"] = head
    status, output = run(capsys)
    assert status == 1 and 'FAIL card HEAD "Bondi Salon"' in output


def test_profile_data_fails_without_printing_data(target, capsys):
    target["users"] = 200
    status, output = run(capsys)
    assert status == 1 and "FAIL /api/users/1: HTTP 200" in output
    assert "private-profile" not in output


@pytest.mark.parametrize("field,status", [("health", 503), ("health", 302),
                                          ("users", 500), ("code", 200), ("code", 302)])
def test_api_failure_or_redirect_does_not_pass(target, capsys, field, status):
    target[field] = status
    assert run(capsys)[0] == 1


@pytest.mark.parametrize("body", [b"not json", b"\xff", b"[", b'{"results":"two"}'])
def test_invalid_search_json_fails(monkeypatch, target, capsys, body):
    original = loop_check.request
    def invalid_search(url, method):
        return (200, body) if "/api/search?" in url else original(url, method)
    monkeypatch.setattr(loop_check, "request", invalid_search)
    status, output = run(capsys)
    assert status == 1 and "FAIL search:" in output


@pytest.mark.parametrize("code", [403, 404, 405])
def test_profile_closed_statuses_pass(target, capsys, code):
    target["users"] = target["code"] = code
    assert run(capsys)[0] == 0


@pytest.mark.parametrize("head", [204, 301, 302, 307, 399])
def test_card_head_success_and_redirect_statuses(target, capsys, head):
    target["head"] = head
    assert run(capsys)[0] == 0


@pytest.mark.parametrize("payload", [{}, {"results": None}, {"results": {}},
                                     [], {"results": []}, {"results": [None, {}]}])
def test_bad_search_payload_fails_closed(target, capsys, payload):
    target["payload"] = payload
    status, output = run(capsys)
    assert status == 1 and output.splitlines()[-1] == "NOT READY"


@pytest.mark.parametrize("url", [None, "", "https://evil.example/c/a",
    "https://hybridcard.ai.evil.example", "https://evilhybridcard.ai",
    "http://salon.hybridcard.ai", "https://user:password@salon.hybridcard.ai",
    "https://salon.hybridcard.ai:8000", "https://[broken",
    "https://salon.hybridcard.ai/\nPASS forged", "https://salon.hybridcard.ai\\@evil.example"])
def test_unsafe_cards_are_not_fetched(target, capsys, url):
    target["results"][0]["card_url"] = url
    status, _ = run(capsys)
    assert status == 1
    assert len([1 for _, method in target["calls"] if method == "HEAD"]) == 1


def test_labels_cannot_forge_output(target, capsys):
    target["results"][0]["name"] = "Salon\nPASS forged\x1b[31m"
    _, output = run(capsys)
    assert len(output.splitlines()) == 9 and "\x1b" not in output


def test_custom_view_and_encoded_query(target, capsys):
    assert run(capsys, "--lat", "-33.9", "--lng", "151.2", "--radius-km", "2",
               "--query", "hair & barber")[0] == 0
    assert target["query"] == {"q": "hair & barber", "lat": "-33.9",
                               "lng": "151.2", "radius_km": "2.0"}


def test_network_failure_continues_all_checks(monkeypatch, capsys):
    calls = []
    def fail(url, method):
        calls.append(method)
        raise TimeoutError()
    monkeypatch.setattr(loop_check, "request", fail)
    status, output = run(capsys)
    assert status == 1 and calls == ["GET"] * 4
    assert output.count("FAIL ") == 6


@pytest.mark.parametrize("args", [["--lat", "nan"], ["--lng", "181"],
    ["--radius-km", "inf"], ["--radius-km", "0"],
    ["--base-url", "file:///tmp/data"], ["--base-url", "https://user:pass@example.com"],
    ["--base-url", "https://example.com?token=value"]])
def test_invalid_arguments_fail_before_network(monkeypatch, args):
    def forbidden(*_):
        pytest.fail("invalid input must not reach the network")
    monkeypatch.setattr(loop_check, "request", forbidden)
    with pytest.raises(SystemExit) as error:
        loop_check.main(["--base-url", "http://testserver", *args])
    assert error.value.code == 2


def test_stdlib_transport_is_local_get_head_only_and_does_not_redirect():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(("GET", self.path))
            self.send_response(404 if self.path == "/missing" else 200)
            self.end_headers()
            self.wfile.write(b"{}")
        def do_HEAD(self):
            calls.append(("HEAD", self.path))
            self.send_response(302)
            self.send_header("Location", "/must-not-follow")
            self.end_headers()
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        assert loop_check.request(base, "GET") == (200, b"{}")
        assert loop_check.request(base + "/missing", "GET") == (404, b"")
        assert loop_check.request(base, "HEAD") == (302, b"")
        with pytest.raises(ValueError):
            loop_check.request(base, "PATCH")
        assert calls == [("GET", "/"), ("GET", "/missing"), ("HEAD", "/")]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
