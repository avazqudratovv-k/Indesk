"""Find and kill processes through /proc. Stdlib only, Linux only.

Killing the process group is not enough: code that runs with the AST check off can start a new
session (setsid) and leave the group, or fork and exit so its children are re-parented. So after
every job the whole tree under the job is stopped and killed, and so is every process that was
re-parented to this server (the server is a "child subreaper", see server.py).
"""

import contextlib
import os
import signal
import time
from collections.abc import Collection

PROC = "/proc"


def snapshot() -> dict[int, tuple[str, int]]:
    """pid -> (state letter, parent pid) for every process visible now."""
    found: dict[int, tuple[str, int]] = {}
    try:
        names = os.listdir(PROC)
    except OSError:
        return found
    for name in names:
        if not name.isdigit():
            continue
        try:
            with open(f"{PROC}/{name}/stat", "rb") as handle:
                raw = handle.read()
        except OSError:
            continue  # gone already
        # "pid (comm) S ppid ...": comm can hold spaces and brackets: split after the last ")"
        fields = raw[raw.rfind(b")") + 2 :].split()
        if len(fields) >= 2 and fields[1].isdigit():
            found[int(name)] = (fields[0].decode(), int(fields[1]))
    return found


def descendants(root: int, snap: dict[int, tuple[str, int]]) -> set[int]:
    children: dict[int, list[int]] = {}
    for pid, (_, parent) in snap.items():
        children.setdefault(parent, []).append(pid)
    found: set[int] = set()
    todo = [root]
    while todo:
        for child in children.get(todo.pop(), []):
            if child not in found:
                found.add(child)
                todo.append(child)
    return found


def _signal(pids: Collection[int], sig: int, protect: Collection[int]) -> None:
    for pid in pids:
        if pid > 1 and pid not in protect:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, sig)


def kill_tree(root: int, protect: Collection[int] = ()) -> None:
    """Stop, then kill, `root` and everything below it. Stopping first keeps the tree from
    forking while it is being collected; the loop repeats until no new process shows up."""
    tree: set[int] = {root}
    for _ in range(20):
        _signal(tree, signal.SIGSTOP, protect)
        snap = snapshot()
        found = {root} | descendants(root, snap)
        if found <= tree:
            break
        tree |= found
    _signal(tree, signal.SIGKILL, protect)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(root, signal.SIGKILL)


def find_strays(me: int, keep: Collection[int]) -> list[int]:
    """Processes re-parented to this server that are not a running job's own runner."""
    return [pid for pid, (_, parent) in snapshot().items() if parent == me and pid not in keep]


def sweep_strays(me: int, keep: Collection[int], seconds: float = 1.0) -> None:
    """Kill and reap every stray (and what is below it). Zombies appear only after the kill, so
    repeat until none is left or the time is up."""
    deadline = time.monotonic() + seconds
    while True:
        strays = find_strays(me, keep)
        if not strays:
            return
        for pid in strays:
            kill_tree(pid, protect=keep)
            with contextlib.suppress(ChildProcessError, OSError):
                os.waitpid(pid, os.WNOHANG)
        if time.monotonic() >= deadline:
            return
        time.sleep(0.02)


def count_processes() -> int:
    return len(snapshot())


def cpu_seconds(pid: int) -> float:
    """User plus system CPU time of a process (a zombie still has it), 0.0 if unknown."""
    try:
        with open(f"{PROC}/{pid}/stat", "rb") as handle:
            raw = handle.read()
        fields = raw[raw.rfind(b")") + 2 :].split()
        # fields[0] is field 3 (state); utime and stime are fields 14 and 15.
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, IndexError, ValueError):
        return 0.0
