"""Who is calling: the client IP, and the CSRF check on write requests."""

import ipaddress
from urllib.parse import urlsplit

from fastapi import Request

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
BODY_TYPES = frozenset({"application/json", "multipart/form-data"})

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_ip(value: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _is_trusted(ip: IPAddress, proxies: list[IPNetwork]) -> bool:
    return any(ip in net for net in proxies)


def client_ip(request: Request, trusted_proxies: list[str]) -> str:
    """The socket peer, unless the peer is a trusted proxy. Then X-Forwarded-For is read from the
    right and the first address that is not a trusted proxy is the client."""
    peer = request.client.host if request.client else "unknown"
    peer_ip = _parse_ip(peer)
    networks = [ipaddress.ip_network(p, strict=False) for p in trusted_proxies]
    forwarded = request.headers.get("x-forwarded-for")
    if peer_ip is None or not forwarded or not _is_trusted(peer_ip, networks):
        return peer
    for part in reversed(forwarded.split(",")):
        ip = _parse_ip(part)
        if ip is None:
            return peer  # garbage in the header: do not guess
        if not _is_trusted(ip, networks):
            return str(ip)
    return peer


def request_origin(request: Request) -> str | None:
    """The Origin header, or the origin of the Referer when there is no Origin."""
    origin = request.headers.get("origin")
    if origin is not None:
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if not referer:
        return None
    parts = urlsplit(referer)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def has_body(request: Request) -> bool:
    length = request.headers.get("content-length")
    return "transfer-encoding" in request.headers or (length not in (None, "0"))


def body_type_allowed(request: Request) -> bool:
    media = request.headers.get("content-type", "").split(";")[0].strip().lower()
    return media in BODY_TYPES
