"""Gateway outcomes and sandbox codes -> run failure reasons. Users see these generic codes only.

| source                          | reason              | run outcome | retry once |
| gateway cap_reached             | daily_cap_user/global | rejected  | no  |
| gateway busy (all 429)          | model_busy          | failed      | no (burns call caps) |
| gateway timeout                 | model_timeout       | failed      | yes |
| gateway model_unavailable       | model_unavailable   | failed      | yes |
| gateway bad_output              | bad_model_output    | failed      | yes |
| gateway bad_input               | input_unusable      | failed      | no  |
| sandbox timeout                 | analysis_failed     | failed      | yes (state timed_out) |
| sandbox forbidden, runtime      | analysis_failed     | failed      | yes |
| sandbox memory, output_too_large| analysis_failed     | failed      | no (same result) |
| sandbox bad_input               | input_unusable      | failed      | no  |
| sandbox unavailable             | sandbox_unavailable | failed      | yes |

P10 treats daily_cap_user, daily_cap_global and model_busy as "busy today". Nothing here has run
against real Gemini; the gateway outcomes are the ones its fake-client tests produce."""

from app.ai.gateway import GatewayError
from app.core.enums import GatewayOutcome, RunOutcome, RunReason, SandboxErrorCode, StepState
from app.runs.agents import AgentFailed
from app.sandbox_client import SandboxError


def failure_from_gateway(error: GatewayError) -> AgentFailed:
    match error.outcome:
        case GatewayOutcome.CAP_REACHED:
            reason = (
                RunReason.DAILY_CAP_GLOBAL
                if error.cap_scope == "global"
                else RunReason.DAILY_CAP_USER
            )
            return AgentFailed(reason, outcome=RunOutcome.REJECTED)
        case GatewayOutcome.BUSY:
            return AgentFailed(RunReason.MODEL_BUSY)
        case GatewayOutcome.TIMEOUT:
            return AgentFailed(RunReason.MODEL_TIMEOUT, retryable=True, state=StepState.TIMED_OUT)
        case GatewayOutcome.BAD_OUTPUT:
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT, retryable=True)
        case GatewayOutcome.BAD_INPUT:
            return AgentFailed(RunReason.INPUT_UNUSABLE)
        case _:  # MODEL_UNAVAILABLE, and OK (not an error: treated as unavailable, never a pass)
            return AgentFailed(RunReason.MODEL_UNAVAILABLE, retryable=True)


def failure_from_sandbox(error: SandboxError) -> AgentFailed:
    match error.code:
        case SandboxErrorCode.TIMEOUT:
            return AgentFailed(RunReason.ANALYSIS_FAILED, retryable=True, state=StepState.TIMED_OUT)
        case SandboxErrorCode.FORBIDDEN | SandboxErrorCode.RUNTIME:
            return AgentFailed(RunReason.ANALYSIS_FAILED, retryable=True)
        case SandboxErrorCode.MEMORY | SandboxErrorCode.OUTPUT_TOO_LARGE:
            return AgentFailed(RunReason.ANALYSIS_FAILED)
        case (
            SandboxErrorCode.BAD_INPUT
            | SandboxErrorCode.ENCRYPTED
            | SandboxErrorCode.TOO_MANY_PAGES
            | SandboxErrorCode.TOO_MUCH_TEXT
            | SandboxErrorCode.UNREADABLE
        ):  # the last four come from PDF parse jobs only (upload time); never from a pandas run
            return AgentFailed(RunReason.INPUT_UNUSABLE)
        case _:  # UNAVAILABLE
            return AgentFailed(RunReason.SANDBOX_UNAVAILABLE, retryable=True)
