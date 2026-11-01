import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ghost import linkcheck


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/moved":
            self.send_response(301)
            self.send_header("Location", "/404")
            self.end_headers()
            return
        code = int(self.path.strip("/") or 200)
        self.send_response(code)
        self.end_headers()
        self.wfile.write(b"x")

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    httpd = HTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(autouse=True)
def allow_local(monkeypatch):
    monkeypatch.setattr(linkcheck, "is_public_host", lambda host: True)


@pytest.mark.parametrize("code,alive", [(200, True), (404, False), (410, False), (500, False), (403, True), (429, True)])
def test_status_codes(site, code, alive):
    assert linkcheck.is_alive(f"{site}/{code}") is alive


def test_a_redirect_is_followed_to_its_target(site):
    assert linkcheck.is_alive(site + "/moved") is False


def test_unknown_host_is_dead(monkeypatch):
    def fail(*a, **k):
        raise socket.gaierror
    monkeypatch.setattr(socket, "getaddrinfo", fail)
    assert linkcheck.is_alive("https://no-such-host.example/") is False


def test_private_address_is_refused(monkeypatch, site):
    monkeypatch.setattr(linkcheck, "is_public_host", lambda host: False)
    assert linkcheck.is_alive(site + "/200") is False


def test_non_web_address_is_refused():
    assert linkcheck.is_alive("ftp://example.org/x") is False
