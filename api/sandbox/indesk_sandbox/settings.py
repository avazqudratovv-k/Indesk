"""Numbers shared by the server and the runner. Stdlib only."""

import os

MAX_BODY_BYTES = 12 * 1024 * 1024  # base64 of 8 MiB of CSV plus the code
MAX_CSV_BYTES = 8 * 1024 * 1024  # a 5 MB cp949 upload grows to about 7.5 MB as UTF-8
MAX_PDF_BYTES = 8 * 1024 * 1024  # the API caps a PDF at 5 MB; this is the hard ceiling
PDF_MAX_PAGES_HARD = 200  # a request may ask for fewer, never more
PDF_MAX_CHARS_HARD = 200_000  # extracted characters; keeps the JSON answer under MAX_RESULT_BYTES
MAX_CODE_CHARS = 100_000
MAX_RESULT_BYTES = 1024 * 1024  # serialized `result`
MAX_STREAM_BYTES = 64 * 1024  # captured stdout, and stderr, each
MAX_CONCURRENT_JOBS = 2
# PDF parse jobs (P14a) run in the separate parser container (parser_server.py): one at a time.
# A second parse is answered "unavailable" at once. It never takes a pandas run's slot: another
# process.
MAX_CONCURRENT_PARSE_JOBS = 1
POOL_THREADS = 4  # started once; spare threads answer /health and "busy" while two jobs run
REQUEST_READ_SECONDS = 10.0  # whole request body, so a slow sender cannot hold a thread

CPU_SECONDS = 5
WALL_SECONDS = 10.0
# Virtual address space of a job. numpy and pandas map a lot of address space they never touch, so
# this is well above their real use but well below the container's memory limit (compose.yaml):
# two jobs at this limit plus the server still fit, so a 4 GB allocation ends as `memory` in the
# job and never as an out-of-memory kill of the container.
ADDRESS_SPACE_BYTES = 1280 * 1024 * 1024
MAX_PROCESSES = 40  # per user id, threads included; the container's pids_limit is the hard cap
MAX_FILE_BYTES = 8 * 1024 * 1024  # one file a job writes
MAX_OPEN_FILES = 128

JOBS_ROOT = "/tmp/jobs"  # noqa: S108  # in the tmpfs
TEST_MODE_VARIABLE = "SANDBOX_TEST_MODE"
OUTCOME_CODES = frozenset(
    {
        "timeout", "memory", "forbidden", "runtime", "output_too_large", "bad_input",
        # PDF parse jobs only (P14a):
        "encrypted", "too_many_pages", "too_much_text", "unreadable",
    }
)  # fmt: skip


def ast_check_enabled(requested: bool) -> bool:
    """A request may switch the AST check off only when the container was started in test mode
    (compose.sandbox-test.yaml). In normal mode the request flag is ignored."""
    return requested if os.environ.get(TEST_MODE_VARIABLE) == "1" else True
