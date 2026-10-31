"""Preview picture for a source article: the image the page itself names for link previews.

Only public web addresses are opened, so a link cannot make the server read your own network.
"""
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

TIMEOUT = 6
MAX_BYTES = 400_000
MAX_HOPS = 3
USER_AGENT = "Mozilla/5.0 (compatible; ghost-app/0.1)"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class _Meta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:url", "twitter:image", "twitter:image:src") and a.get("content"):
            self.found.setdefault(key, a["content"].strip())


def is_public_host(host):
    """True if every address the name resolves to is a public internet address."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


def fetch_page(url, allow_private=False):
    """Download a page (follows up to 3 redirects, checking each address). Returns (final url, html)."""
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(MAX_HOPS + 1):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("Not a web address.")
        if not allow_private and not is_public_host(parts.hostname):
            raise ValueError("Not a public address.")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                if "html" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError("Not an HTML page.")
                return url, response.read(MAX_BYTES).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location") if 300 <= error.code < 400 else None
            if not location:
                raise
            url = urllib.parse.urljoin(url, location)
    raise ValueError("Too many redirects.")


def find_image(url, fetch=fetch_page):
    """Address of the article's preview image, or "" if there is none."""
    if not url:
        return ""
    try:
        final_url, html = fetch(url)
        parser = _Meta()
        parser.feed(html)
    except (OSError, ValueError, urllib.error.URLError):
        return ""
    for key in ("og:image", "og:image:url", "twitter:image", "twitter:image:src"):
        if key in parser.found:
            image = urllib.parse.urljoin(final_url, parser.found[key])
            if urllib.parse.urlsplit(image).scheme in ("http", "https"):
                return image
    return ""
