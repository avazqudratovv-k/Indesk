"""The AST check (defense in depth only; the container is the boundary) and the test-mode switch."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sandbox"))

from indesk_sandbox import ast_check, settings  # noqa: E402

REJECTED = [
    "import os",
    "from os import path",
    "import subprocess\nsubprocess.run(['ls'])",
    "__import__('os')",
    "open('/etc/passwd')",
    "exec('1')",
    "eval('1')",
    "compile('1', 'x', 'exec')",
    "getattr(df, 'to_csv')",
    "setattr(df, 'x', 1)",
    "globals()",
    "locals()",
    "vars(df)",
    "dir(df)",
    "input()",
    "breakpoint()",
    "df.__class__",
    "df.__class__.__mro__[1].__subclasses__()",
    "x = ().__class__.__bases__[0]",
    "(lambda: 0).__globals__",
    "type(df)",
    "os.system('id')",
    "sys.exit()",
    "socket.socket()",
    "ctypes.CDLL(None)",
    "'{0.__class__}'.format(df)",
    "df.to_csv('/tmp/x')",
    "df.to_pickle('/tmp/x')",
    "pd.read_csv('/etc/passwd')",
    "pd.read_pickle('/tmp/x')",
    "pd.io.common.os.system('id')",
    "df.eval('a + 1')",
    "df.query('a > 1')",
    "np.load('/tmp/x')",
    "np.fromfile('/tmp/x')",
    "df._data",
    "class A: pass",
    "async def f(): pass",
    "def f(__x): return 1",
    "memoryview(b'')",
    "(yield)",
]

ACCEPTED = [
    "result = df.groupby('line')['boardings'].sum().to_dict()",
    "result = {'n': int(len(df)), 'mean': float(df['boardings'].mean())}",
    "top = df.sort_values('boardings', ascending=False).head(3)\nresult = top['station'].tolist()",
    "def total(frame):\n    return int(frame['boardings'].sum())\nresult = total(df)",
    "result = [int(x) for x in np.arange(3)]",
    'result = f"{len(df)} rows"',
]


@pytest.mark.parametrize("code", REJECTED)
def test_rejected(code: str) -> None:
    with pytest.raises(ast_check.ForbiddenCode):
        ast_check.check(code)


@pytest.mark.parametrize("code", ACCEPTED)
def test_accepted(code: str) -> None:
    ast_check.check(code)


def test_syntax_error_is_not_forbidden() -> None:
    with pytest.raises(ast_check.BadSyntax):
        ast_check.check("def (")


def test_the_ast_flag_is_ignored_unless_the_container_is_in_test_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(settings.TEST_MODE_VARIABLE, raising=False)
    assert settings.ast_check_enabled(False) is True
    for value in ("0", "true", "", "2"):
        monkeypatch.setenv(settings.TEST_MODE_VARIABLE, value)
        assert settings.ast_check_enabled(False) is True
    monkeypatch.setenv(settings.TEST_MODE_VARIABLE, "1")
    assert settings.ast_check_enabled(False) is False
    assert settings.ast_check_enabled(True) is True
