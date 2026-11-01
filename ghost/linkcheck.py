"""Check that a source link opens a real page.

A link counts as dead only on clear evidence: the host does not exist, the server
answers 404 or 410, or it answers with a server error. Sites that refuse automated
requests (401, 403, 429) or are slow are kept, because the page may exist.
Only public web addresses are opened, as in preview.py.
"""
import socket
import urllib.error
import urllib.parse
import urllib.request

from ghost.preview import MAX_HOPS, USER_AGENT, _NoRedirect, is_public_host

TIMEOUT = 6
DEAD_CODES = {404, 410}


def is_alive(url):
    """False if the link is clearly dead, True otherwise."""
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(MAX_HOPS + 1):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return False
        try:
            socket.getaddrinfo(parts.hostname, None)
        except OSError:
            return False  # the host name does not exist
        if not is_public_host(parts.hostname):
            return False
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with opener.open(request, timeout=TIMEOUT) as response:
                response.read(1)
                return True
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location") if 300 <= error.code < 400 else None
            if location:
                url = urllib.parse.urljoin(url, location)
                continue
            return not (error.code in DEAD_CODES or error.code >= 500)
        except (OSError, ValueError):
            return True  # slow or unreachable right now: not proof the page is gone
    return True
