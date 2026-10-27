"""The sandbox HTTP server. Stdlib only. This process serves POST /run (and GET /health). PDF
parsing is a different process with the same code: parser_server.py serves ONLY POST /parse-pdf,
in its own container on its own network (P14a fix). Neither process has the other's route.

Request:  JSON {"job_id": str, "code": str, "csv_b64": str, "check_ast": bool (optional)}
          /parse-pdf: JSON {"job_id": str, "pdf_b64": str, "max_pages": int, "max_chars": int}
Response: 200 {"ok": true, "result": <json>, "duration_ms": n}
          200 {"ok": false, "error": "<fixed code>", "duration_ms": n}
          400 bad_input (malformed request), 413 bad_input (too large), 503 unavailable (busy).
Never a traceback, a message, or any output of the job.

Every job runs in a fresh subprocess (runner.py) with its own limits, an empty environment and its
own working directory in the tmpfs. The server never runs model code itself.

The container is the security boundary (see compose.yaml). The kernel is shared with the host.
This server and the jobs run as the same user, so a job can signal this server; the compose file
restarts it, and the server holds no secrets.
"""

import base64
import binascii
import contextlib
import ctypes
import json
import logging
import os
import queue
import re
import selectors
import shutil
import struct
import subprocess  # noqa: S404  # starting the runner is this module's job
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

from indesk_sandbox import procs, settings

logger = logging.getLogger("indesk.sandbox.server")

RUNNER = str(Path(__file__).with_name("runner.py"))
PARSE_RUNNER = str(Path(__file__).with_name("parse_runner.py"))
JOB_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
PR_SET_DUMPABLE = 4
PR_SET_CHILD_SUBREAPER = 36
HEADER = struct.Struct(">II")
PARSE_HEADER = struct.Struct(">III")  # max pages, max characters, PDF length
CHUNK = 64 * 1024

# What a job gets as its environment. Nothing is inherited. The thread counts keep numpy from
# starting a pool of threads that would not fit under the process limit.
JOB_ENV = {
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "LANG": "C.UTF-8",
}


class Registry:
    """The runner processes that are alive. A process re-parented to the server that is NOT in
    here is a stray (escaped from a job) and gets killed."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active: set[int] = set()

    def sweep(self) -> None:
        with self.lock:
            keep = set(self.active)
            procs.sweep_strays(os.getpid(), keep)


REGISTRY = Registry()
SLOTS = threading.BoundedSemaphore(settings.MAX_CONCURRENT_JOBS)
PARSE_SLOTS = threading.BoundedSemaphore(settings.MAX_CONCURRENT_PARSE_JOBS)  # parser process only


class Outcome:
    def __init__(self, result: Any = None, error: str | None = None) -> None:
        self.result = result
        self.error = error


def _set_nonblocking(fd: int) -> None:
    os.set_blocking(fd, False)


def _classify_exit(returncode: int, cpu: float) -> str:
    """The runner died without writing an outcome. Killed by the CPU limit: timeout. Killed by
    anything else (the kernel, a failed allocation inside C code): memory."""
    if returncode < 0:
        return "timeout" if cpu >= settings.CPU_SECONDS - 0.5 else "memory"
    return "runtime"


def _parse_outcome(raw: bytes) -> Outcome:
    kind, body = raw[:1], raw[1:]
    if kind == b"E":
        code = body.decode("ascii", "replace")
        return Outcome(error=code if code in settings.OUTCOME_CODES else "runtime")
    if kind == b"K":
        try:
            return Outcome(result=json.loads(body))
        except (ValueError, RecursionError, MemoryError):
            return Outcome(error="runtime")
    return Outcome(error="runtime")


def _announced(result: bytearray) -> int:
    return int(struct.unpack(">I", bytes(result[:4]))[0])


def _complete(result: bytearray) -> bool:
    """The whole message (4-byte length, then that many bytes) has arrived."""
    return len(result) >= 4 and len(result) >= 4 + _announced(result)


def _pump(
    proc: subprocess.Popen[bytes], result_read: int, frame: bytes
) -> tuple[bytes, str | None]:
    """Feed the job's stdin and read its pipes until the result pipe closes, a cap is hit, or the
    wall time is up. Returns (result bytes, error code or None)."""
    assert proc.stdin and proc.stdout and proc.stderr  # noqa: S101  # all three are PIPE
    stdin_fd, out_fd, err_fd = proc.stdin.fileno(), proc.stdout.fileno(), proc.stderr.fileno()
    for fd in (stdin_fd, out_fd, err_fd, result_read):
        _set_nonblocking(fd)
    view = memoryview(frame)
    sent = 0
    totals = {out_fd: 0, err_fd: 0}
    result = bytearray()
    deadline = time.monotonic() + settings.WALL_SECONDS
    with selectors.DefaultSelector() as sel:
        sel.register(stdin_fd, selectors.EVENT_WRITE)
        for fd in (out_fd, err_fd, result_read):
            sel.register(fd, selectors.EVENT_READ)
        while result_read in sel.get_map() and not _complete(result):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return b"", "timeout"
            for key, _ in sel.select(remaining):
                fd = key.fd
                if fd == stdin_fd:
                    try:
                        sent += os.write(fd, view[sent : sent + CHUNK])
                    except BlockingIOError:
                        continue
                    except OSError:
                        sent = len(frame)  # the job closed stdin early
                    if sent >= len(frame):
                        sel.unregister(fd)
                        proc.stdin.close()
                    continue
                try:
                    data = os.read(fd, CHUNK)
                except BlockingIOError:
                    continue
                if not data:
                    sel.unregister(fd)
                    continue
                if fd == result_read:
                    result += data
                    if len(result) >= 4 and _announced(result) > settings.MAX_RESULT_BYTES + 1:
                        return b"", "output_too_large"
                else:
                    totals[fd] += len(data)  # counted, then thrown away
                    if totals[fd] > settings.MAX_STREAM_BYTES:
                        return b"", "output_too_large"
    return (bytes(result[4:]) if _complete(result) else b""), None


def run_job(code: str, csv_bytes: bytes, check_ast: bool) -> Outcome:
    ast_on = settings.ast_check_enabled(check_ast)
    code_bytes = code.encode("utf-8")
    frame = HEADER.pack(len(code_bytes), len(csv_bytes)) + code_bytes + csv_bytes
    return _execute(RUNNER, [str(int(ast_on))], frame)


def parse_job(pdf_bytes: bytes, max_pages: int, max_chars: int) -> Outcome:
    frame = PARSE_HEADER.pack(max_pages, max_chars, len(pdf_bytes)) + pdf_bytes
    return _execute(PARSE_RUNNER, [], frame)


def _execute(runner: str, extra_args: list[str], frame: bytes) -> Outcome:
    """Start one runner process with the frame on its stdin and collect its single outcome."""
    try:
        job_dir = tempfile.mkdtemp(dir=settings.JOBS_ROOT)
        result_read, result_write = os.pipe()
    except OSError:
        return Outcome(error="unavailable")
    proc: subprocess.Popen[bytes] | None = None
    try:
        env = {**JOB_ENV, "HOME": job_dir, "TMPDIR": job_dir}
        try:
            with REGISTRY.lock:
                proc = subprocess.Popen(  # noqa: S603  # fixed argument list, no shell
                    [sys.executable, "-E", "-s", "-B", runner, str(result_write), *extra_args],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    pass_fds=(result_write,),
                    cwd=job_dir,
                    env=env,
                    start_new_session=True,
                )
                REGISTRY.active.add(proc.pid)
        except OSError:
            return Outcome(error="unavailable")
        finally:
            os.close(result_write)
        raw, error = _pump(proc, result_read, frame)
        if error is not None:
            procs.kill_tree(proc.pid)
        cpu = procs.cpu_seconds(proc.pid)
        procs.kill_tree(proc.pid)
        try:
            returncode = proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            returncode = -9
        if error is not None:
            return Outcome(error=error)
        if raw:
            return _parse_outcome(raw)
        return Outcome(error=_classify_exit(returncode, cpu))
    finally:
        if proc is not None:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    with contextlib.suppress(OSError):
                        stream.close()
            with REGISTRY.lock:
                REGISTRY.active.discard(proc.pid)
        os.close(result_read)
        REGISTRY.sweep()
        shutil.rmtree(job_dir, ignore_errors=True)


def _decode_request(body: bytes) -> tuple[str, str, bytes, bool] | None:
    try:
        data = json.loads(body)
        job_id, code, csv_b64 = data["job_id"], data["code"], data["csv_b64"]
        check_ast = data.get("check_ast", True)
        if not (isinstance(job_id, str) and JOB_ID.fullmatch(job_id)):
            return None
        if not (isinstance(code, str) and 0 < len(code) <= settings.MAX_CODE_CHARS):
            return None
        if not (isinstance(csv_b64, str) and isinstance(check_ast, bool)):
            return None
        csv_bytes = base64.b64decode(csv_b64, validate=True)
    except (ValueError, KeyError, TypeError, binascii.Error, RecursionError):
        return None
    if not csv_bytes or len(csv_bytes) > settings.MAX_CSV_BYTES:
        return None
    return job_id, code, csv_bytes, check_ast


def _decode_parse_request(body: bytes) -> tuple[str, bytes, int, int] | None:
    try:
        data = json.loads(body)
        job_id, pdf_b64 = data["job_id"], data["pdf_b64"]
        max_pages, max_chars = data["max_pages"], data["max_chars"]
        if not (isinstance(job_id, str) and JOB_ID.fullmatch(job_id) and isinstance(pdf_b64, str)):
            return None
        for number, hard in (
            (max_pages, settings.PDF_MAX_PAGES_HARD),
            (max_chars, settings.PDF_MAX_CHARS_HARD),
        ):
            if isinstance(number, bool) or not isinstance(number, int) or not 0 < number <= hard:
                return None
        pdf_bytes = base64.b64decode(pdf_b64, validate=True)
    except (ValueError, KeyError, TypeError, binascii.Error, RecursionError):
        return None
    if not pdf_bytes or len(pdf_bytes) > settings.MAX_PDF_BYTES:
        return None
    return job_id, pdf_bytes, max_pages, max_chars


def health() -> dict[str, Any]:
    rss_kb = 0
    with contextlib.suppress(OSError, ValueError, IndexError):
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss_kb = int(line.split()[1])
    return {"ok": True, "rss_kb": rss_kb, "procs": procs.count_processes()}


class Handler(BaseHTTPRequestHandler):
    timeout = settings.REQUEST_READ_SECONDS  # a socket timeout on every read and write
    protocol_version = "HTTP/1.0"  # one request per connection
    # path -> (job slot, method name). The base class serves no job route; each process picks ONE
    # subclass, so the sandbox has no /parse-pdf and the parser has no /run.
    routes: ClassVar[dict[str, tuple[threading.BoundedSemaphore, str]]] = {}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return  # no access log: a path or an address is not needed, and a body must never appear

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes | None:
        """Exactly Content-Length bytes within the read deadline, or None."""
        raw = self.headers.get("Content-Length", "")
        if "Transfer-Encoding" in self.headers or not raw.isdigit():
            return None
        length = int(raw)
        if length > settings.MAX_BODY_BYTES:
            return None
        deadline = time.monotonic() + settings.REQUEST_READ_SECONDS
        chunks: list[bytes] = []
        remaining = length
        while remaining > 0:
            if time.monotonic() > deadline:
                return None
            chunk = self.rfile.read(min(remaining, CHUNK))
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, health())
        else:
            self._send(404, {"ok": False, "error": "bad_input"})

    def do_POST(self) -> None:
        route = self.routes.get(self.path)
        if route is None:
            self._send(404, {"ok": False, "error": "bad_input"})
            return
        slots, method = route
        if not slots.acquire(blocking=False):
            self._send(503, {"ok": False, "error": "unavailable"})
            return
        try:
            getattr(self, method)()
        finally:
            slots.release()

    def _run(self) -> None:
        started = time.monotonic()
        try:
            body = self._read_body()
        except (OSError, TimeoutError):
            return  # the sender went away or was too slow; nothing to answer
        request = None if body is None else _decode_request(body)
        if request is None:
            self._send(400, {"ok": False, "error": "bad_input", "duration_ms": 0})
            return
        job_id, code, csv_bytes, check_ast = request
        self._finish(job_id, run_job(code, csv_bytes, check_ast), started)

    def _parse(self) -> None:
        started = time.monotonic()
        try:
            body = self._read_body()
        except (OSError, TimeoutError):
            return
        request = None if body is None else _decode_parse_request(body)
        if request is None:
            self._send(400, {"ok": False, "error": "bad_input", "duration_ms": 0})
            return
        job_id, pdf_bytes, max_pages, max_chars = request
        self._finish(job_id, parse_job(pdf_bytes, max_pages, max_chars), started)

    def _finish(self, job_id: str, outcome: Outcome, started: float) -> None:
        elapsed = int((time.monotonic() - started) * 1000)
        if outcome.error == "unavailable":
            status, payload = 503, {"ok": False, "error": "unavailable"}
        elif outcome.error is not None:
            status, payload = 200, {"ok": False, "error": outcome.error, "duration_ms": elapsed}
        else:
            status, payload = 200, {"ok": True, "result": outcome.result, "duration_ms": elapsed}
        logger.info("job %s %s %dms", job_id, outcome.error or "ok", elapsed)  # nothing else
        try:
            self._send(status, payload)
        except (ValueError, RecursionError):  # a result that cannot be written back out
            self._send(200, {"ok": False, "error": "runtime", "duration_ms": elapsed})


class RunHandler(Handler):
    routes = {"/run": (SLOTS, "_run")}


class ParseHandler(Handler):
    routes = {"/parse-pdf": (PARSE_SLOTS, "_parse")}


class PoolServer(HTTPServer):
    """HTTPServer with a fixed set of handler threads, started once. Creating a thread per request
    would fail while a runaway job holds the user's process limit."""

    def __init__(self, address: tuple[str, int], handler: type[Handler]) -> None:
        super().__init__(address, handler)
        self.pending: queue.Queue[tuple[Any, Any]] = queue.Queue(maxsize=16)
        for _ in range(settings.POOL_THREADS):
            threading.Thread(target=self._worker, daemon=True).start()

    def process_request(self, request: Any, client_address: Any) -> None:
        try:
            self.pending.put_nowait((request, client_address))
        except queue.Full:
            self.shutdown_request(request)

    def _worker(self) -> None:
        while True:
            request, client_address = self.pending.get()
            try:
                self.finish_request(request, client_address)
            except Exception:  # noqa: BLE001  # one bad connection must not end the thread
                logger.error("request failed")
            finally:
                self.shutdown_request(request)


def prepare_process() -> None:
    """Become the parent of every orphan (so strays can be found), and keep jobs from reading this
    process's memory or descriptors through /proc."""
    libc = ctypes.CDLL(None)
    libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
    # Owner can create and enter but not list: a job cannot list the folder to find another job's.
    root = Path(settings.JOBS_ROOT)
    root.mkdir(mode=0o300, exist_ok=True)
    root.chmod(0o300)


def serve(handler: type[Handler], name: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    prepare_process()
    server = PoolServer(("0.0.0.0", 8080), handler)  # noqa: S104  # inside the container; no port is published
    logger.info("%s listening", name)
    server.serve_forever()


def main() -> None:
    serve(RunHandler, "sandbox")


if __name__ == "__main__":
    main()
