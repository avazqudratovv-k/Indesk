"""One job, in its own process. Started by server.py as `python -E -s -B runner.py <fd> <ast 0|1>`.

It sets its own limits first (no preexec_fn in the threaded server), reads the job from stdin,
runs the code, and writes ONE outcome to the result pipe: a 4-byte length, then b"K" + JSON or
b"E" + a fixed code.
Nothing else leaves this process: stdout and stderr are counted and thrown away by the server.
"""

import builtins
import contextlib
import ctypes
import io
import json
import os
import resource
import struct
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indesk_sandbox import ast_check, settings  # noqa: E402

HEADER = struct.Struct(">II")  # code length, CSV length
PR_SET_DUMPABLE = 4

# Taken out of the builtins the code sees while the AST check is on. With the check off (test mode
# only) the code gets the real builtins.
_HIDDEN_BUILTINS = frozenset(
    {
        "open", "exec", "eval", "compile", "__import__", "getattr", "setattr", "delattr",
        "hasattr", "globals", "locals", "vars", "dir", "input", "breakpoint", "help", "exit",
        "quit", "memoryview", "type", "super", "object", "classmethod", "staticmethod",
        "property", "__build_class__", "copyright", "credits", "license",
    }
)  # fmt: skip


def _limit(kind: int, soft: int, hard: int | None = None) -> None:
    resource.setrlimit(kind, (soft, soft if hard is None else hard))


def apply_limits() -> None:
    """The CPU limit sends SIGXCPU at 5 s and SIGKILL two seconds later."""
    _limit(resource.RLIMIT_CPU, settings.CPU_SECONDS, settings.CPU_SECONDS + 2)
    _limit(resource.RLIMIT_AS, settings.ADDRESS_SPACE_BYTES)
    _limit(resource.RLIMIT_NPROC, settings.MAX_PROCESSES)
    _limit(resource.RLIMIT_FSIZE, settings.MAX_FILE_BYTES)
    _limit(resource.RLIMIT_NOFILE, settings.MAX_OPEN_FILES)
    _limit(resource.RLIMIT_CORE, 0)
    # Not dumpable: other processes of the same user (a second job) cannot read /proc/<pid>/fd,
    # cwd, environ or mem of this one.
    with contextlib.suppress(Exception):
        ctypes.CDLL(None).prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)


def read_exact(count: int) -> bytes:
    chunks = []
    while count > 0:
        chunk = os.read(0, min(count, 1 << 20))
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        count -= len(chunk)
    return b"".join(chunks)


def _plain(value: object) -> object:
    """json.dumps hook: numpy numbers and arrays become plain Python. Anything else is an error."""
    import numpy as np  # noqa: PLC0415  # imported after the limits are set

    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError


def build_namespace(csv_bytes: bytes, ast_on: bool) -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    try:
        # index_col=False: a file whose every row ends with an extra empty cell (header 6, rows 7)
        # would otherwise lose its first column to the index and shift all the others.
        df = pd.read_csv(io.BytesIO(csv_bytes), index_col=False)
    except Exception as error:
        raise ValueError("bad csv") from error
    safe = {k: v for k, v in vars(builtins).items() if not ast_on or k not in _HIDDEN_BUILTINS}
    return {"__builtins__": safe, "df": df, "pd": pd, "np": np}


def run(code: str, csv_bytes: bytes, ast_on: bool) -> tuple[bytes, bytes]:
    """Returns (b"K", JSON) or (b"E", code)."""
    if ast_on:
        try:
            ast_check.check(code)
        except ast_check.ForbiddenCode:
            return b"E", b"forbidden"
        except ast_check.BadSyntax:
            return b"E", b"bad_input"
    try:
        compiled = compile(code, "<job>", "exec")
        namespace = build_namespace(csv_bytes, ast_on)
    except ValueError:
        return b"E", b"bad_input"
    except SyntaxError:
        return b"E", b"bad_input"
    try:
        exec(compiled, namespace)  # noqa: S102  # the whole point; see the module docstring
        if "result" not in namespace:
            return b"E", b"runtime"
        payload = json.dumps(namespace["result"], default=_plain, allow_nan=False).encode()
    except MemoryError:
        return b"E", b"memory"
    except BaseException:  # noqa: BLE001  # includes SystemExit from the job's own code
        return b"E", b"runtime"
    if len(payload) > settings.MAX_RESULT_BYTES:
        return b"E", b"output_too_large"
    return b"K", payload


def main(argv: list[str]) -> None:
    result_fd, ast_on = int(argv[1]), argv[2] == "1"
    apply_limits()
    try:
        code_length, csv_length = HEADER.unpack(read_exact(HEADER.size))
        code = read_exact(code_length).decode("utf-8")
        csv_bytes = read_exact(csv_length)
        kind, body = run(code, csv_bytes, ast_on)
    except MemoryError:
        kind, body = b"E", b"memory"
    except Exception:  # noqa: BLE001
        kind, body = b"E", b"bad_input"
    with contextlib.suppress(OSError):
        message = kind + body
        # Length first: the server stops reading at the end of the message, because a process that
        # forked from the job may still hold this pipe open.
        os.write(result_fd, struct.pack(">I", len(message)) + message)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv)
