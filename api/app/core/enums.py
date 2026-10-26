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
    UNAVAILABLE = "unavailable"  # set by the client when the service cannot be reached


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
