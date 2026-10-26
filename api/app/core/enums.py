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
