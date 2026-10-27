"""One PDF parse job, in its own process. Started by server.py as
`python -E -s -B parse_runner.py <fd>`.

Same shape as runner.py: it sets its own limits first, reads the job from stdin (a 12-byte header
of max pages, max characters and PDF length, then the PDF), and writes ONE outcome to the result
pipe: a 4-byte length, then b"K" + JSON or b"E" + a fixed code. No model code runs here; the input
is an untrusted file, and the only thing that leaves is page text.

An encrypted PDF is refused without trying a password (out of scope for v1). Nothing in the PDF is
executed: pypdf reads text and never runs the file's JavaScript or opens links.
"""

import contextlib
import io
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indesk_sandbox import settings  # noqa: E402
from indesk_sandbox.runner import apply_limits, read_exact  # noqa: E402

HEADER = struct.Struct(">III")  # max pages, max characters, PDF length


def _clean(text: str) -> str:
    """A lone surrogate cannot be written as UTF-8; replace it so the answer always can."""
    return text.encode("utf-8", "replace").decode("utf-8")


def parse(pdf: bytes, max_pages: int, max_chars: int) -> tuple[bytes, bytes]:
    """Returns (b"K", JSON {"page_count", "pages"}) or (b"E", code)."""
    from pypdf import PdfReader  # noqa: PLC0415  # imported after the limits are set

    try:
        reader = PdfReader(io.BytesIO(pdf), strict=False)
        if reader.is_encrypted:
            return b"E", b"encrypted"
        count = len(reader.pages)
        if count < 1:
            return b"E", b"unreadable"
        if count > max_pages:
            return b"E", b"too_many_pages"
        pages: list[str] = []
        total = 0
        for page in reader.pages:
            text = _clean(page.extract_text() or "")
            total += len(text)
            if total > max_chars:
                return b"E", b"too_much_text"
            pages.append(text)
        payload = json.dumps(
            {"page_count": count, "pages": pages}, ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except MemoryError:
        return b"E", b"memory"
    except Exception:  # noqa: BLE001  # a damaged file can raise anything, RecursionError included
        return b"E", b"unreadable"
    if len(payload) > settings.MAX_RESULT_BYTES:
        return b"E", b"output_too_large"
    return b"K", payload


def main(argv: list[str]) -> None:
    result_fd = int(argv[1])
    apply_limits()
    try:
        max_pages, max_chars, length = HEADER.unpack(read_exact(HEADER.size))
        pdf = read_exact(length)
        kind, body = parse(pdf, max_pages, max_chars)
    except MemoryError:
        kind, body = b"E", b"memory"
    except Exception:  # noqa: BLE001
        kind, body = b"E", b"bad_input"
    with contextlib.suppress(OSError):
        message = kind + body
        os.write(result_fd, struct.pack(">I", len(message)) + message)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv)
