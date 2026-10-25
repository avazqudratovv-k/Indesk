"""Stop an oversized upload while it arrives. The multipart parser would otherwise copy the whole
body to disk before any route code runs, whoever is calling and however big the body is."""

from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import ErrorCode, error_response

# Room for the multipart boundaries, headers and the consent field around the file itself.
MULTIPART_OVERHEAD = 64 * 1024


class BodyLimitMiddleware:
    """For one method and path: refuse at once when Content-Length is over the limit, and cut the
    request off when the bytes that actually arrive pass it (chunked, or a header that lies)."""

    def __init__(self, app: ASGIApp, *, method: str, path: str, limit: Callable[[], int]) -> None:
        self.app = app
        self.method = method
        self.path = path
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != self.method or scope["path"] != self.path:
            await self.app(scope, receive, send)
            return
        limit = self.limit()
        declared = dict(scope["headers"]).get(b"content-length")
        too_large = error_response(413, ErrorCode.FILE_TOO_LARGE)
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await too_large(scope, receive, send)
            return

        received = 0
        exceeded = False
        forwarded = False

        async def counting_receive() -> Message:
            # Over the limit: tell the app the client went away. Whatever the app then answers
            # (FastAPI turns a half-read body into a 400) is dropped and replaced by the 413 below.
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal forwarded
            if exceeded and not forwarded:
                return
            forwarded = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not exceeded or forwarded:
                raise
        if exceeded and not forwarded:
            await too_large(scope, receive, send)
