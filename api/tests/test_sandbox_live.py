"""Tests against the RUNNING sandbox service, started in test mode (compose.sandbox-test.yaml).
Not part of the default `pytest`. Run:

    docker compose -f compose.yaml -f compose.sandbox-test.yaml up -d --build sandbox
    docker compose -f compose.yaml -f compose.sandbox-test.yaml run --rm worker pytest -m sandbox

Each hostile case runs with the AST check ON and OFF. OFF is possible only in test mode; it shows
what the container limits do when the code gets past the AST check. After every test the next
normal job must still work and the sandbox must have no leftover processes.
"""

import base64
import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from app.core.config import get_settings
from app.core.enums import SandboxErrorCode
from app.sandbox_client import SandboxError, SandboxOk, run_pandas

pytestmark = pytest.mark.sandbox

CSV = b"station,line,boardings\nHapjeong,2,100\nSeongsu,2,90\nMagok,9,80\nGimpo,9,70\n"
GROUPBY = "result = df.groupby('line')['boardings'].sum().to_dict()"


def sandbox_url() -> str:
    return get_settings().sandbox_url.rstrip("/")


def submit(code: str, csv: bytes = CSV, *, ast: bool = True) -> dict[str, Any]:
    """Raw call, so a test can set check_ast. Returns the JSON answer plus the HTTP status."""
    body = json.dumps(
        {
            "job_id": str(uuid.uuid4()),
            "code": code,
            "csv_b64": base64.b64encode(csv).decode(),
            "check_ast": ast,
        }
    ).encode()
    request = urllib.request.Request(f"{sandbox_url()}/run", data=body, method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            answer: dict[str, Any] = json.loads(response.read())
            answer["status"] = response.status
    except urllib.error.HTTPError as error:
        answer = json.loads(error.read())
        answer["status"] = error.code
    answer["wall"] = time.monotonic() - started
    return answer


def health() -> dict[str, Any]:
    with urllib.request.urlopen(f"{sandbox_url()}/health", timeout=5) as response:
        data: dict[str, Any] = json.loads(response.read())
    return data


def wait_for_baseline(baseline: int) -> int:
    count = health()["procs"]
    for _ in range(40):
        count = health()["procs"]
        if count <= baseline:
            break
        time.sleep(0.1)
    return int(count)


@pytest.fixture(scope="module")
def baseline_procs() -> int:
    try:
        first = submit("import os\nresult = 1", ast=False)
    except OSError as error:
        pytest.fail(f"the sandbox service is not reachable: {type(error).__name__}")
    assert first.get("ok") is True, (
        "the sandbox is not in test mode: start it with compose.sandbox-test.yaml"
    )
    return int(health()["procs"])


@pytest.fixture(autouse=True)
def _next_job_still_works(baseline_procs: int) -> Iterator[None]:
    yield
    answer = submit(GROUPBY)
    assert answer["ok"] is True, answer
    assert answer["result"] == {"2": 190, "9": 150}
    assert wait_for_baseline(baseline_procs) <= baseline_procs, "leftover processes in the sandbox"


# ---- the normal job ----


def test_groupby_returns_the_right_result() -> None:
    answer = submit("result = {'rows': int(len(df)), 'total': int(df['boardings'].sum())}")
    assert answer["ok"] is True
    assert answer["result"] == {"rows": 4, "total": 340}
    assert answer["status"] == 200


def test_a_trailing_empty_cell_on_every_row_does_not_shift_the_columns() -> None:
    # Header of 3, every row has a 4th empty cell (the Seoul file's shape). Plain read_csv would
    # use the first column as the index and move every value one name to the left.
    csv = b'"day","station","boardings"\r\n"20260901","A","10",""\n"20260902","B","20",""\n'
    answer = submit(
        "result = {'cols': list(df.columns), 'shape': list(df.shape),"
        " 'day': int(df['day'].iloc[0]), 'station': str(df['station'].iloc[1]),"
        " 'sum': int(df['boardings'].sum())}",
        csv,
    )
    assert answer["ok"] is True, answer
    assert answer["result"] == {
        "cols": ["day", "station", "boardings"],
        "shape": [2, 3],
        "day": 20260901,
        "station": "B",
        "sum": 30,
    }


def test_the_client_runs_a_job_end_to_end() -> None:
    result = run_pandas(GROUPBY, CSV)
    assert isinstance(result, SandboxOk)
    assert result.result == {"2": 190, "9": 150}


def test_numpy_numbers_and_a_list_come_back_as_plain_json() -> None:
    answer = submit("result = [np.int64(3), float(df['boardings'].mean()), None, 'x']")
    assert answer["result"] == [3, 85.0, None, "x"]


def test_syntax_error_and_a_missing_result_are_fixed_codes() -> None:
    assert submit("def (")["error"] == "bad_input"
    assert submit("x = 1")["error"] == "runtime"
    assert submit("result = 1 / 0")["error"] == "runtime"
    assert submit("result = {1, 2}")["error"] == "runtime"  # a set is not JSON


def test_a_bad_csv_and_a_malformed_request_are_bad_input() -> None:
    assert submit("result = 1", b"\xff\xfe\x00 not a csv \x00")["error"] == "bad_input"
    request = urllib.request.Request(f"{sandbox_url()}/run", data=b"{not json", method="POST")
    with pytest.raises(urllib.error.HTTPError) as info:
        urllib.request.urlopen(request, timeout=5)
    assert info.value.code == 400
    assert json.loads(info.value.read()) == {"ok": False, "error": "bad_input", "duration_ms": 0}


def test_a_big_result_is_output_too_large() -> None:
    for ast in (True, False):
        answer = submit("result = ['x' * 1000] * 5000", ast=ast)  # about 5 MB serialized
        assert answer["error"] == "output_too_large"


def test_the_switch_works_only_in_test_mode() -> None:
    assert submit("import os\nresult = 1", ast=True)["error"] == "forbidden"
    assert submit("import os\nresult = 1", ast=False)["ok"] is True


# ---- hostile code: each case with the AST check ON and OFF ----

NETWORK = """
import socket
out = {}
for key, target in (("ip", ("1.1.1.1", 80)), ("ip6", ("2606:4700:4700::1111", 80))):
    try:
        socket.create_connection(target, timeout=3).close()
        out[key] = "connected"
    except OSError:
        out[key] = "refused"
try:
    socket.gethostbyname("example.com")
    out["dns"] = "resolved"
except OSError:
    out["dns"] = "failed"
result = out
"""


def test_no_internet() -> None:
    assert submit(NETWORK, ast=True)["error"] == "forbidden"
    answer = submit(NETWORK, ast=False)
    assert answer["result"] == {"ip": "refused", "ip6": "refused", "dns": "failed"}


INTERNAL_NAMES = """
import socket
out = {}
NAMES = ("db", "redis", "api", "parser", "scheduler", "postgres", "indesk-db-1", "indesk-redis-1")
for name in NAMES:
    try:
        socket.gethostbyname(name)
        out[name] = "resolved"
    except OSError:
        out[name] = "failed"
result = out
"""


def test_the_sandbox_has_no_parse_route() -> None:
    """PDF parsing is the parser container's job (P14a); the sandbox serves /run only."""
    body = json.dumps(
        {"job_id": str(uuid.uuid4()), "pdf_b64": "JVBERg==", "max_pages": 1, "max_chars": 1}
    )
    request = urllib.request.Request(
        f"{sandbox_url()}/parse-pdf", data=body.encode(), method="POST"
    )
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=10)  # noqa: S310  # our own sandbox
    assert caught.value.code == 404


def test_db_redis_and_api_names_do_not_resolve() -> None:
    assert submit(INTERNAL_NAMES, ast=True)["error"] == "forbidden"
    answer = submit(INTERNAL_NAMES, ast=False)
    assert set(answer["result"].values()) == {"failed"}, answer["result"]


WRITES = """
out = {}
for path in ("/srv/x", "/etc/x", "/usr/x", "/x", "/var/x", "/proc/self/x", "/app/x"):
    try:
        with open(path, "w") as handle:
            handle.write("x")
        out[path] = "written"
    except OSError:
        out[path] = "refused"
with open("inside.txt", "w") as handle:  # the job's own folder, in the tmpfs
    handle.write("x")
out["cwd"] = "written"
result = out
"""


def test_cannot_write_outside_the_tmpfs() -> None:
    assert submit(WRITES, ast=True)["error"] == "forbidden"
    result = submit(WRITES, ast=False)["result"]
    assert result.pop("cwd") == "written"
    assert set(result.values()) == {"refused"}, result


ENVIRON = """
import os
raw = open("/proc/self/environ", "rb").read().decode().split("\\0")
names = sorted(item.split("=", 1)[0] for item in raw if item)
parent = open("/proc/%d/environ" % os.getppid(), "rb").read().decode()
result = {"names": names, "env": sorted(os.environ), "parent_readable": bool(parent)}
"""


def test_no_secrets_in_the_job_environment() -> None:
    assert submit(ENVIRON, ast=True)["error"] == "forbidden"
    answer = submit(ENVIRON, ast=False)
    allowed = {"HOME", "LANG", "TMPDIR"} | {f"{n}_NUM_THREADS" for n in ("MKL", "OMP", "OPENBLAS")}
    if answer.get("ok"):
        assert set(answer["result"]["names"]) <= allowed
        assert set(answer["result"]["env"]) <= allowed
    else:
        # The server's own /proc files are not dumpable, so reading them may fail: also fine.
        assert answer["error"] == "runtime"
    for secret in ("DATABASE_URL", "AUTH_SECRET", "REDIS_URL", "GEMINI_API_KEY", "SANDBOX_TEST"):
        assert secret not in json.dumps(answer)


def test_cpu_loop_ends_at_the_cpu_limit() -> None:
    for ast in (True, False):
        answer = submit("while True:\n    pass", ast=ast)
        assert answer["error"] == "timeout"
        assert 4 <= answer["wall"] < 9


def test_four_gigabytes_ends_as_memory_not_a_container_kill() -> None:
    for ast in (True, False):
        assert submit("result = int(np.ones(4 * 10**9).sum())", ast=ast)["error"] == "memory"
    assert submit("x = bytearray(4 * 10**9)\nresult = 1", ast=False)["error"] == "memory"
    assert submit("x = [0] * (4 * 10**9)\nresult = 1", ast=True)["error"] == "memory"


FORK_BOMB_WAIT = """
import os, time
kids = 0
for _ in range(500):
    try:
        pid = os.fork()
    except OSError:
        break
    if pid == 0:
        try:
            os.setsid()
        except OSError:
            pass
        while True:
            pass
    kids += 1
time.sleep(30)
result = kids
"""

FORK_ESCAPE_AND_EXIT = """
import os
for _ in range(5):
    if os.fork() == 0:
        os.setsid()
        if os.fork() == 0:
            while True:
                pass
        os._exit(0)
result = "left"
"""


def test_fork_bomb_is_contained() -> None:
    assert submit(FORK_BOMB_WAIT, ast=True)["error"] == "forbidden"
    answer = submit(FORK_BOMB_WAIT, ast=False)
    assert answer["error"] in {"timeout", "runtime", "memory"}
    assert answer["wall"] < 20
    # The autouse check after this test runs a normal job and requires no leftover processes.


def test_processes_that_escape_the_group_are_killed_after_the_job() -> None:
    assert submit(FORK_ESCAPE_AND_EXIT, ast=True)["error"] == "forbidden"
    answer = submit(FORK_ESCAPE_AND_EXIT, ast=False)
    assert answer["ok"] is True and answer["result"] == "left"
    # The leftovers are spinning in new sessions. They must be gone shortly after the job.


def test_huge_print_ends_quickly_and_server_memory_stays_flat() -> None:
    before = health()["rss_kb"]
    for ast in (True, False):
        answer = submit("while True:\n    print('x' * 100000)", ast=ast)
        assert answer["error"] == "output_too_large"
        assert answer["wall"] < 4
    answer = submit("import sys\nwhile True:\n    sys.stderr.write('y' * 100000)", ast=False)
    assert answer["error"] == "output_too_large"
    assert answer["wall"] < 4
    after = health()["rss_kb"]
    assert after - before < 30_000, f"server memory grew {after - before} kB"


def test_sleep_hits_the_wall_timeout() -> None:
    assert submit("import time\ntime.sleep(60)\nresult = 1", ast=True)["error"] == "forbidden"
    answer = submit("import time\ntime.sleep(60)\nresult = 1", ast=False)
    assert answer["error"] == "timeout"
    assert 9 <= answer["wall"] < 14


# ---- two jobs ----

SNOOP = """
import os, glob
found = []
mark = ("SECRETMARK", "CSVMARK")
def look(path):
    try:
        if os.path.isdir(path):
            names = os.listdir(path)
            if any(m in n for n in names for m in mark):
                found.append(("name", path))
            return
        data = open(path, "rb").read(200000)
        if any(m.encode() in data for m in mark):
            found.append(("data", path))
    except OSError:
        pass
listing = {}
for folder in ("/tmp", "/tmp/jobs"):
    try:
        listing[folder] = len(os.listdir(folder))
    except OSError:
        listing[folder] = "denied"
for pid in filter(str.isdigit, os.listdir("/proc")):
    if int(pid) == os.getpid():
        continue
    for sub in ("environ", "cmdline", "mem", "maps"):
        look("/proc/%s/%s" % (pid, sub))
    look("/proc/%s/cwd" % pid)
    for fd in glob.glob("/proc/%s/fd/*" % pid):
        look(fd)
    for path in glob.glob("/proc/%s/cwd/*" % pid):
        look(path)
result = {"found": found, "listing": listing}
"""

HOLD = """
import os, time
with open("SECRETMARK.txt", "w") as handle:
    handle.write("SECRETMARK")
time.sleep(6)
result = os.getcwd().count("SECRETMARK")
"""


def test_two_jobs_cannot_see_each_others_files_or_data() -> None:
    outcome: dict[str, dict[str, Any]] = {}

    def hold() -> None:
        outcome["hold"] = submit(HOLD, b"a,b\nCSVMARK,1\n", ast=False)

    thread = threading.Thread(target=hold)
    thread.start()
    time.sleep(2)
    outcome["snoop"] = submit(SNOOP, b"a,b\nx,1\n", ast=False)
    thread.join()
    assert outcome["hold"]["ok"] is True
    assert outcome["snoop"]["ok"] is True, outcome["snoop"]
    assert outcome["snoop"]["result"]["found"] == []
    assert outcome["snoop"]["result"]["listing"]["/tmp/jobs"] == "denied"


def test_a_later_job_finds_nothing_left_by_an_earlier_one() -> None:
    submit("open('LEFTOVER.txt', 'w').write('x')\nresult = 1", ast=False)
    answer = submit(
        "import os\nresult = [sorted(os.listdir('.')), 'LEFTOVER.txt' in os.listdir('/tmp')]",
        ast=False,
    )
    assert answer["result"] == [[], False]


def test_a_third_concurrent_job_gets_503_and_the_client_says_unavailable() -> None:
    results: list[Any] = []

    def slow() -> None:
        results.append(run_pandas("while True:\n    pass", CSV))

    threads = [threading.Thread(target=slow) for _ in range(2)]
    for thread in threads:
        thread.start()
    time.sleep(1.5)
    third = run_pandas(GROUPBY, CSV)
    for thread in threads:
        thread.join()
    assert isinstance(third, SandboxError)
    assert third.code is SandboxErrorCode.UNAVAILABLE
    assert all(isinstance(r, SandboxError) and r.code is SandboxErrorCode.TIMEOUT for r in results)
