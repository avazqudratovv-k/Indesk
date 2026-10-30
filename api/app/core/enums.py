"""Closed vocabularies shared by the database (CHECK constraints) and the API schemas.

One definition per list, so a value can never exist in one layer and not the other.
Values follow docs/ai/DATA.md. Agent keys in the database: manager, vision, data, retrieval, critic.
"""

from enum import StrEnum


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    PAYG = "payg"
    CUSTOM = "custom"


class Lang(StrEnum):
    EN = "en"
    KO = "ko"
    JA = "ja"
    RU = "ru"
    UZ = "uz"


class Theme(StrEnum):
    LIGHT = "light"
    DARK = "dark"


class DefaultView(StrEnum):
    SIMPLE = "simple"
    DETAILED = "detailed"


class UploadStatus(StrEnum):
    UPLOADED = "uploaded"
    READY = "ready"
    DELETED = "deleted"


class Moderation(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    BLOCKED = "blocked"


class UploadMime(StrEnum):
    CSV = "text/csv"
    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"
    TXT = "text/plain"


class RunMode(StrEnum):
    ASK = "ask"
    CHECK = "check"
    COMPARE = "compare"


class QuestionType(StrEnum):
    NEW = "new"
    EXPLAIN = "explain"
    REFORMAT = "reformat"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"


class RunOutcome(StrEnum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    NOT_ANSWERABLE = "not_answerable"
    NEEDS_BETTER_INPUT = "needs_better_input"
    REJECTED = "rejected"
    FAILED = "failed"


class FileRole(StrEnum):
    SUBJECT = "subject"
    SOURCE = "source"
    A = "a"
    B = "b"


class AgentKey(StrEnum):
    MANAGER = "manager"
    VISION = "vision"
    DATA = "data"
    RETRIEVAL = "retrieval"
    CRITIC = "critic"


class StepState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class StepKind(StrEnum):
    SAY = "say"
    TOOL = "tool"
    FLAG = "flag"


class Bubble(StrEnum):
    OWL_SPLIT = "owlSplit"
    OWL_MERGE = "owlMerge"


class EvidenceType(StrEnum):
    TABLE = "table"
    CHART = "chart"
    CODE = "code"
    IMAGE_BOXES = "image_boxes"
    PASSAGE = "passage"
    DIFF = "diff"
    CRITIC_NOTE = "critic_note"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReportTemplate(StrEnum):
    PLAIN = "plain"
    CLASSIC = "classic"
    COMPACT = "compact"
    SUMMARY = "summary"


class ReportTypeface(StrEnum):
    CLEAN = "clean"
    SERIF = "serif"
    TECHNICAL = "technical"


class TextSize(StrEnum):
    S = "s"
    M = "m"
    L = "l"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    FLAGGED = "flagged"
    UNVERIFIED = "unverified"
    MISMATCH = "mismatch"


class ClaimOrigin(StrEnum):
    ANSWER = "answer"
    DOCUMENT = "document"


class AiPurpose(StrEnum):
    ROUTE = "route"
    PLAN = "plan"
    PICK = "pick"
    COMPUTE = "compute"
    VISION = "vision"
    CRITIC = "critic"
    EXTRACT_CLAIMS = "extract_claims"
    EMBED = "embed"


class JobClass(StrEnum):
    """Which model chain a request uses (DECISIONS #27, #28): light jobs or main reasoning."""

    LIGHT = "light"
    MAIN = "main"
    EMBED = "embed"  # embeddings (P14a part 2): one model, retries only, no fallback


class EmbedTask(StrEnum):
    """The task type sent with an embedding request: documents and queries are embedded
    differently (P14a part 2). The values are the API's own words."""

    DOCUMENT = "RETRIEVAL_DOCUMENT"
    QUERY = "RETRIEVAL_QUERY"


class AiCallStatus(StrEnum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    ERROR = "error"


class UsageKind(StrEnum):
    RUN = "run"
    CREDIT_PURCHASE = "credit_purchase"


class SandboxErrorCode(StrEnum):
    """Fixed outcomes of a sandbox job. The sandbox never returns a traceback or a message."""

    TIMEOUT = "timeout"
    MEMORY = "memory"
    FORBIDDEN = "forbidden"
    RUNTIME = "runtime"
    OUTPUT_TOO_LARGE = "output_too_large"
    BAD_INPUT = "bad_input"
    # PDF parse jobs only (P14a). The sandbox says what is wrong with the file, never more.
    ENCRYPTED = "encrypted"
    TOO_MANY_PAGES = "too_many_pages"
    TOO_MUCH_TEXT = "too_much_text"
    UNREADABLE = "unreadable"
    UNAVAILABLE = "unavailable"  # set by the client when the service cannot be reached, or is busy


class GatewayOutcome(StrEnum):
    """What the Gemini gateway returns to its caller. Never an exception, never a model message."""

    OK = "ok"
    BUSY = "busy"  # every model in the chain answered 429
    TIMEOUT = "timeout"  # the 35 s budget ran out, or a model timed out and none answered
    # No key, no client, no model, 5xx answers, or the cap store is down.
    MODEL_UNAVAILABLE = "model_unavailable"
    CAP_REACHED = "cap_reached"  # a daily model-call cap; the result says which scope
    BAD_OUTPUT = "bad_output"  # a model answered, but not with usable output
    BAD_INPUT = "bad_input"  # the prompt is over the character cap; nothing was sent


class FailureKind(StrEnum):
    """Why one model request failed, as stored in ai_calls.failure_kind. A closed code: never a
    response body, a URL, a header or a key. Set by the model client, filled in by the gateway."""

    HTTP_400 = "http_400"
    HTTP_401 = "http_401"
    HTTP_403 = "http_403"
    HTTP_404 = "http_404"
    HTTP_4XX = "http_4xx"  # any other 4xx except 429 (that one is status rate_limited)
    HTTP_5XX = "http_5xx"
    TRANSPORT = "transport"  # the request could not be made or the connection broke
    BAD_JSON = "bad_json"  # HTTP 200 but the body is unreadable or has no text
    TOO_LARGE = "too_large"  # HTTP 200 but the body is over the size limit
    OTHER = "other"


class ModelFailure(StrEnum):
    """Why one request to one model failed. Set by the model client, read by the gateway."""

    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    OTHER = "other"  # any other HTTP status or a transport error
    BAD_RESPONSE = "bad_response"  # HTTP 200 but unreadable or too large


class CapDecision(StrEnum):
    RESERVED = "reserved"
    USER_CAP = "user_cap"
    GLOBAL_CAP = "global_cap"
    UNAVAILABLE = "unavailable"  # the counter store failed; the gateway fails closed


class RunReason(StrEnum):
    """Why a run ended without an answer. A fixed code, never a message: the browser translates it.
    The first two come with outcome `rejected`, the rest with `failed` (DATA.md: a cap refuses)."""

    DAILY_CAP_USER = "daily_cap_user"
    DAILY_CAP_GLOBAL = "daily_cap_global"
    MODEL_BUSY = "model_busy"  # every model answered 429
    MODEL_TIMEOUT = "model_timeout"
    MODEL_UNAVAILABLE = "model_unavailable"  # also: no agents are configured yet
    BAD_MODEL_OUTPUT = "bad_model_output"
    ANALYSIS_FAILED = "analysis_failed"  # the sandbox could not run the generated code
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    INPUT_UNUSABLE = "input_unusable"
    STEP_CAP = "step_cap"
    RUN_TIMEOUT = "run_timeout"
    WORKER_LOST = "worker_lost"
    BUDGET_EXCEEDED = "budget_exceeded"  # max_tokens_per_run
    INTERNAL_ERROR = "internal_error"


class TraceKey(StrEnum):
    """The closed list of trace line keys. The browser holds the text for each one."""

    PLAN = "plan"
    DISPATCH = "dispatch"
    READ_CSV = "readCsv"
    RUN_PYTHON = "runPython"
    TOP3 = "top3"
    MERGE = "merge"
    READY = "ready"
    STEP_STARTED = "stepStarted"  # the executor opens an agent that failed before saying anything
    STEP_FAILED = "stepFailed"
    STOPPED = "stopped"  # the closing line of every run that did not end in a normal answer
    VERIFY = "verify"  # Cat checks the claims (P9); args: claims, verified
    # Hound (P14a part 2). Keys and args follow the web mock (messages workspace.live.events).
    SEARCH = "search"  # args: pages, matched (+ mode)
    BEST_PASSAGE = "bestPassage"  # args: page, score, similarity
    SEARCH_FAILED = "searchFailed"  # args: reason, attempt
    # Hound notes (P14b), said before its closing line.
    KEYWORD_ONLY_SIZE = "keywordOnlySize"  # keyword-only because of document size; args: reason
    CHUNKS_SKIPPED = "chunksSkipped"  # chunks too big to embed, found by words; args: count


class ReportReason(StrEnum):
    """Why Cat did not verify a claim: a closed code stored in a `critic_note` evidence payload.
    The browser translates it; no sentence is ever stored (P9)."""

    ROWS_MISMATCH = "rows_mismatch"  # the calculation did not use every row of the file
    BAD_REFERENCE = "bad_reference"  # a cell reference that does not exist
    NO_NUMERIC_EVIDENCE = "no_numeric_evidence"  # the claim cites no number
    LABEL_MISSING = "label_missing"  # the claim does not name the row it cites
    NUMBER_MISMATCH = "number_mismatch"  # a number in the text is not in the cited cells
    RANKING_UNCHECKED = "ranking_unchecked"  # "most", "least"...: not the extreme of its column
    # Document claims (P14a part 2): the quote and page the writer gave are checked against the
    # stored text of the PDF.
    QUOTE_NOT_FOUND = "quote_not_found"  # the quote is on no page of the document
    PAGE_MISMATCH = "page_mismatch"  # the quote is in the document, but not on the cited page
    BAD_PAGE = "bad_page"  # the cited page does not exist
    QUOTE_TOO_SHORT = "quote_too_short"  # under 12 characters once spaces are ignored
    NUMBER_NOT_IN_QUOTE = "number_not_in_quote"  # a number in the claim is not in its quote
    NO_QUOTE = "no_quote"  # the claim cites no quote


class EvidenceMethod(StrEnum):
    """How the numbers behind a table were computed: the plan's task word (Owl)."""

    RANK = "rank"
    AGGREGATE = "aggregate"
    TREND = "trend"
    COMPARE_GROUPS = "compare_groups"
    COUNT = "count"
    DESCRIBE = "describe"
