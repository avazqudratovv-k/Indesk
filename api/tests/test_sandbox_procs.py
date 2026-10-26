"""kill_tree reaches processes that left the process group (setsid), and sweep_strays kills
orphans re-parented to this process. Needs Linux /proc, which the api container has."""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sandbox"))

from indesk_sandbox import procs  # noqa: E402

# Parent starts a child in a NEW session (escapes killpg), which starts a grandchild; all sleep.
TREE = """
import os, time
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        time.sleep(60)
    time.sleep(60)
time.sleep(60)
"""


def alive(pid: int) -> bool:
    state = procs.snapshot().get(pid)
    return state is not None and state[0] != "Z"


def test_kill_tree_reaches_a_child_in_a_new_session() -> None:
    root = subprocess.Popen([sys.executable, "-c", TREE], start_new_session=True)  # noqa: S603
    try:
        time.sleep(1)
        below = procs.descendants(root.pid, procs.snapshot())
        assert len(below) == 2
        procs.kill_tree(root.pid)
        root.wait(timeout=5)
        deadline = time.monotonic() + 3
        while any(alive(p) for p in below) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not any(alive(p) for p in below)
    finally:
        if root.poll() is None:
            root.kill()


def wait_for(condition: Callable[[], bool], seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def test_sweep_strays_kills_orphans_and_spares_kept_pids() -> None:
    from ctypes import CDLL  # noqa: PLC0415

    CDLL(None).prctl(36, 1, 0, 0, 0)  # become the parent of orphans, as the server does
    me = os.getpid()
    kept = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])  # noqa: S603
    # Other tests may have left children of this process (when pytest is PID 1 of the container,
    # every orphan in the container is one), so only what this test adds is counted.
    before = set(procs.find_strays(me, {kept.pid}))
    orphan_script = (
        "import os, time\n"
        "if os.fork() == 0:\n    os.setsid(); time.sleep(60)\n"
        "else:\n    os._exit(0)\n"
    )
    subprocess.run([sys.executable, "-c", orphan_script], check=True, timeout=10)  # noqa: S603
    new: set[int] = set()

    def orphan_arrived() -> bool:
        new.update(set(procs.find_strays(me, {kept.pid})) - before)
        return bool(new)

    try:
        assert wait_for(orphan_arrived), "the orphan was never re-parented to this process"
        assert len(new) == 1
        (orphan,) = new
        assert alive(orphan)
        procs.sweep_strays(me, {kept.pid})
        assert wait_for(lambda: procs.find_strays(me, {kept.pid}) == [])
        assert orphan not in procs.snapshot()  # killed and reaped
        assert kept.poll() is None  # the kept process was left alone
    finally:
        kept.send_signal(signal.SIGKILL)
        kept.wait()
