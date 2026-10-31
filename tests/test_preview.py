import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ghost import preview


def page(head):
    return f"<html><head>{head}</head><body></body></html>"


def finder(html, final="https://site.org/a/b"):
    return lambda url: (final, html)


def test_og_image():
    html = page('<meta property="og:image" content="https://cdn.site.org/pic.jpg">')
    assert preview.find_image("https://site.org/a", finder(html)) == "https://cdn.site.org/pic.jpg"


def test_twitter_image_is_the_fallback():
    html = page('<meta name="twitter:image" content="https://cdn.site.org/t.jpg">')
    assert preview.find_image("https://site.org/a", finder(html)) == "https://cdn.site.org/t.jpg"


def test_og_image_wins_over_twitter_image():
    html = page('<meta name="twitter:image" content="https://x.org/t.jpg"><meta property="og:image" content="https://x.org/o.jpg">')
    assert preview.find_image("https://site.org/a", finder(html)) == "https://x.org/o.jpg"


def test_relative_address_is_completed():
    html = page('<meta property="og:image" content="/img/p.png">')
    assert preview.find_image("https://site.org/a", finder(html)) == "https://site.org/img/p.png"


def test_no_image_gives_empty():
    assert preview.find_image("https://site.org/a", finder(page("<title>x</title>"))) == ""


def test_unsafe_image_address_is_refused():
    for bad in ("javascript:alert(1)", "data:image/png;base64,AAAA", "file:///etc/passwd"):
        html = page(f'<meta property="og:image" content="{bad}">')
        assert preview.find_image("https://site.org/a", finder(html)) == ""


def test_empty_url_and_fetch_errors_give_empty():
    assert preview.find_image("") == ""

    def boom(url):
        raise OSError("offline")
    assert preview.find_image("https://site.org/a", boom) == ""


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "0.0.0.0"])
def test_private_addresses_are_not_public(host):
    assert preview.is_public_host(host) is False


def test_public_address_is_public():
    assert preview.is_public_host("8.8.8.8") is True


def test_fetch_refuses_private_and_non_web_addresses():
    with pytest.raises(ValueError):
        preview.fetch_page("http://127.0.0.1:1/")
    with pytest.raises(ValueError):
        preview.fetch_page("file:///etc/passwd")
    with pytest.raises(ValueError):
        preview.fetch_page("ftp://example.org/x")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
        elif self.path == "/loop":
            self.send_response(302)
            self.send_header("Location", "/loop")
            self.end_headers()
        elif self.path == "/image":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(b"x")
        else:
            body = page('<meta property="og:image" content="/pic.jpg">').encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)


@pytest.fixture(scope="module")
def local():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_fetch_follows_a_redirect(local):
    url, html = preview.fetch_page(local + "/redirect", allow_private=True)
    assert url == local + "/final" and "og:image" in html


def test_fetch_stops_a_redirect_loop(local):
    with pytest.raises(ValueError, match="redirects"):
        preview.fetch_page(local + "/loop", allow_private=True)


def test_fetch_refuses_non_html(local):
    with pytest.raises(ValueError, match="HTML"):
        preview.fetch_page(local + "/image", allow_private=True)


def test_end_to_end_with_a_local_page(local):
    found = preview.find_image(local + "/page", lambda u: preview.fetch_page(u, allow_private=True))
    assert found == local + "/pic.jpg"
