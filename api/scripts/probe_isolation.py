"""DEV TOOL. Stdlib only. Prints what THIS container can reach, for the isolation checks of the
parser and sandbox networks. Run it inside the container being checked, for example:

    docker compose exec -T parser python - < api/scripts/probe_isolation.py

Names that should NOT resolve are printed as "no"; a connection to the internet as "refused"."""

import json
import socket

NAMES = ("api", "db", "redis", "sandbox", "parser", "worker", "scheduler")
out: dict[str, str] = {}
for name in NAMES:
    try:
        socket.gethostbyname(name)
        out[name] = "resolves"
    except OSError:
        out[name] = "no"
for key, target in (
    ("internet-ip", ("1.1.1.1", 80)),
    ("internet-ip6", ("2606:4700:4700::1111", 80)),
):
    try:
        socket.create_connection(target, timeout=3).close()
        out[key] = "CONNECTED"
    except OSError:
        out[key] = "refused"
try:
    socket.gethostbyname("example.com")
    out["internet-dns"] = "RESOLVES"
except OSError:
    out["internet-dns"] = "no"
print(json.dumps(out))
