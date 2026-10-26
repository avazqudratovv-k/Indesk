"""A check of model-written code before it runs. Stdlib only.

DEFENSE IN DEPTH ONLY. A deny-list over Python syntax cannot be complete, and this one is not the
security boundary. The container is (no network, read-only root filesystem, dropped capabilities,
memory, CPU and process limits). The container shares the kernel of the host. This check rejects
the obvious attempts early with a fixed code, so honest mistakes and simple attacks never run.
"""

import ast

FORBIDDEN_NAMES = frozenset(
    {
        # Dynamic code, files, and ways to reach attributes by string.
        "open", "exec", "eval", "compile", "__import__", "getattr", "setattr", "delattr",
        "hasattr", "globals", "locals", "vars", "dir", "input", "breakpoint", "help", "exit",
        "quit", "memoryview", "type", "super", "object", "classmethod", "staticmethod",
        "property",
        # Modules that reach the system, the network or the interpreter.
        "os", "sys", "subprocess", "socket", "shutil", "pathlib", "importlib", "builtins",
        "ctypes", "pickle", "marshal", "signal", "threading", "multiprocessing", "resource",
        "io", "posix", "platform", "inspect", "gc", "pty", "fcntl", "mmap", "select", "ssl",
        "urllib", "http", "requests", "asyncio", "tempfile", "glob", "runpy", "code",
    }
)  # fmt: skip

# Attribute names that read or write files, run code, or open a way around the checks.
FORBIDDEN_ATTRIBUTES = frozenset(
    {
        "eval", "query", "format", "format_map", "style", "io", "core", "compat", "util",
        "testing", "plotting", "lib", "ctypeslib", "f2py", "distutils", "system", "popen",
        "fork", "exec", "spawn", "load", "loadtxt", "genfromtxt", "fromfile", "memmap", "save",
        "savetxt", "savez", "savez_compressed", "tofile", "dump", "dumps", "to_csv", "to_excel",
        "to_pickle", "to_parquet", "to_hdf", "to_sql", "to_feather", "to_orc", "to_stata",
        "to_xml", "to_html", "to_latex", "to_markdown", "to_clipboard", "to_gbq", "to_json",
        "to_xarray", "open", "register_extension", "get_option", "set_option", "option_context",
    }
)  # fmt: skip

# Attribute names starting with these are I/O readers: read_csv, read_pickle, read_sql, ...
FORBIDDEN_ATTRIBUTE_PREFIXES = ("read_", "_")

FORBIDDEN_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.AsyncFunctionDef,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Await,
    ast.Yield,
    ast.YieldFrom,
)


class ForbiddenCode(Exception):  # noqa: N818  # a verdict, not an error condition
    """The code uses something outside the allow-list. Carries no detail by design."""


class BadSyntax(Exception):  # noqa: N818  # a verdict, not an error condition
    """The code does not parse."""


def check(code: str) -> None:
    """Return None if the code is acceptable; raise ForbiddenCode or BadSyntax."""
    try:
        tree = ast.parse(code, mode="exec")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        raise BadSyntax from None
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise ForbiddenCode
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id.startswith("__")):
            raise ForbiddenCode
        if isinstance(node, ast.Attribute) and (
            node.attr in FORBIDDEN_ATTRIBUTES or node.attr.startswith(FORBIDDEN_ATTRIBUTE_PREFIXES)
        ):
            raise ForbiddenCode
        if isinstance(node, ast.arg) and node.arg.startswith("__"):
            raise ForbiddenCode
        if isinstance(node, ast.alias):
            raise ForbiddenCode
