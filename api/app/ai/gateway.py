"""The ONE place the backend asks a model. `Gateway.ask` never raises: it returns GatewayOk or
GatewayError with one fixed outcome. Everything is metadata-only: it logs and stores the model,
an outcome code, the duration, token counts and the run id, never a prompt, an answer or the key.

Per request: size check, key and chain check (the light or the main chain, by job class), then
for each model in order: reserve one cap slot (atomic, fail closed), call the client with what is
left of the total budget, write one ai_calls row, and fall to the next model on 429, 5xx, timeout
or any other failure. A model that answers with unusable output stops the chain (BAD_OUTPUT);
the agent layer owns the one retry.

NOT VERIFIED against real Gemini. Tests use a fake client."""

import logging
import time
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.ai.caps import SessionFactory, reserve_call
from app.ai.client import ClientFailure, ClientOk, EmbedOk, ModelClient
from app.ai.config import ModelChains, ModelSpec, load_model_chains
from app.ai.records import record_attempt
from app.core.clock import quota_day
from app.core.config import Limits, Settings
from app.core.enums import (
    AiCallStatus,
    AiPurpose,
    CapDecision,
    EmbedTask,
    FailureKind,
    GatewayOutcome,
    JobClass,
    ModelFailure,
)

logger = logging.getLogger("indesk.ai")

_CALL_STATUS = {
    ModelFailure.RATE_LIMITED: AiCallStatus.RATE_LIMITED,
    ModelFailure.TIMEOUT: AiCallStatus.TIMEOUT,
    ModelFailure.SERVER_ERROR: AiCallStatus.ERROR,
    ModelFailure.OTHER: AiCallStatus.ERROR,
    ModelFailure.BAD_RESPONSE: AiCallStatus.ERROR,
}


# The chain a request uses when the caller does not name a job class (DECISIONS #27, #28).
PURPOSE_CLASS: dict[AiPurpose, JobClass] = {
    AiPurpose.ROUTE: JobClass.LIGHT,
    AiPurpose.PLAN: JobClass.LIGHT,
    AiPurpose.PICK: JobClass.LIGHT,
    AiPurpose.EXTRACT_CLAIMS: JobClass.LIGHT,
    AiPurpose.COMPUTE: JobClass.MAIN,
    AiPurpose.VISION: JobClass.MAIN,
    AiPurpose.CRITIC: JobClass.MAIN,
    AiPurpose.EMBED: JobClass.EMBED,
}

# A refusal that retrying the same model cannot fix: the key, request or model name is wrong.
_NOT_TRANSIENT = frozenset(
    {
        FailureKind.HTTP_400,
        FailureKind.HTTP_401,
        FailureKind.HTTP_403,
        FailureKind.HTTP_404,
        FailureKind.HTTP_4XX,
    }
)


class GatewayOk(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    ok: Literal[True] = True
    outcome: Literal[GatewayOutcome.OK] = GatewayOutcome.OK
    text: str = Field(repr=False)
    parsed: BaseModel | None = Field(
        default=None, repr=False
    )  # set when a response model was given
    model: str
    attempts: int
    tokens_in: int
    tokens_out: int
    duration_ms: int


class GatewayError(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[False] = False
    outcome: GatewayOutcome
    cap_scope: Literal["user", "global"] | None = None  # set with CAP_REACHED
    attempts: int = 0
    duration_ms: int = 0


GatewayResult = GatewayOk | GatewayError


class EmbedGatewayOk(BaseModel):
    """One vector per text, in order. `attempts` counts requests, retries included."""

    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    outcome: Literal[GatewayOutcome.OK] = GatewayOutcome.OK
    vectors: list[list[float]] = Field(repr=False)
    model: str
    attempts: int
    tokens_in: int
    duration_ms: int


EmbedGatewayResult = EmbedGatewayOk | GatewayError


# What a failure means when the client did not name a cause (a fake client, or an old code path).
_DEFAULT_KIND = {
    ModelFailure.SERVER_ERROR: FailureKind.HTTP_5XX,
    ModelFailure.OTHER: FailureKind.OTHER,
    ModelFailure.BAD_RESPONSE: FailureKind.BAD_JSON,
}


class Gateway:
    def __init__(
        self,
        *,
        api_key: SecretStr | None,
        chains: ModelChains | None,
        limits: Limits,
        session_factory: SessionFactory,
        client: ModelClient | None,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], date] = quota_day,
    ) -> None:
        self._api_key = api_key
        self._chains = chains
        self._limits = limits
        self._sessions = session_factory
        self._client = client
        self._clock = clock
        self._today = today

    def __repr__(self) -> str:
        return "Gateway()"

    def is_configured(self) -> bool:
        """True when a key, the chains and a client exist, so a request could be sent. Callers use
        it to fail early, before they do work that only a model answer would need."""
        key = self._api_key
        return (
            key is not None
            and bool(key.get_secret_value().strip())
            and self._chains is not None
            and self._client is not None
        )

    def embed_model(self) -> str | None:
        """The configured embedding model, or None when there is none."""
        chains = self._chains
        return chains.embed.spec.name if chains is not None and chains.embed is not None else None

    def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        purpose: AiPurpose,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        response_model: type[BaseModel] | None = None,
        job_class: JobClass | None = None,
    ) -> GatewayResult:
        started = self._clock()
        job_class = job_class or PURPOSE_CLASS.get(purpose, JobClass.MAIN)
        try:
            return self._ask(
                prompt, system, purpose, user_id, run_id, response_model, job_class, started
            )
        except Exception:  # noqa: BLE001  # the contract is "never raises"
            logger.error("ai gateway failed code=%s", "AI_GATEWAY_INTERNAL")
            return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started)

    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
    ) -> EmbedGatewayResult:
        """Embed `texts` with the one embedding model. Never raises. The model is not a chain: a
        failed request is retried on the SAME model up to its `attempts`, never on another one
        (vectors of two models cannot be compared). Each request takes a cap slot and writes one
        ai_calls row (purpose embed, with an estimated cost)."""
        started = self._clock()
        try:
            return self._embed(texts, task, user_id, run_id, started)
        except Exception:  # noqa: BLE001  # the contract is "never raises"
            logger.error("ai gateway failed code=%s", "AI_GATEWAY_INTERNAL")
            return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started)

    # ---- internals ----

    def _embed(
        self,
        texts: list[str],
        task: EmbedTask,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        started: float,
    ) -> EmbedGatewayResult:
        if not isinstance(texts, list) or not texts:
            return self._error(GatewayOutcome.BAD_INPUT, started)
        if any(not isinstance(t, str) or not t.strip() for t in texts):
            return self._error(GatewayOutcome.BAD_INPUT, started)
        if any(len(t) > self._limits.max_prompt_chars for t in texts):
            return self._error(GatewayOutcome.BAD_INPUT, started)
        key = self._api_key
        if key is None or not key.get_secret_value().strip():
            return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started)
        if self._chains is None or self._chains.embed is None or self._client is None:
            return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started)
        chain = self._chains.embed
        spec = chain.spec
        deadline = started + chain.total_budget_seconds
        vectors: list[list[float]] = []
        tokens_in = requests = 0
        for first in range(0, len(texts), spec.batch_size):
            batch = texts[first : first + spec.batch_size]
            failures: list[ModelFailure] = []
            budget_gone = False
            for number in range(1, spec.attempts + 1):
                if self._clock() >= deadline:
                    budget_gone = True
                    break
                decision = reserve_call(
                    self._sessions, user_id=user_id, day=self._today(),
                    per_user=self._limits.daily_calls_per_user,
                    per_day=self._limits.daily_calls_global,
                )  # fmt: skip
                if decision is CapDecision.UNAVAILABLE:
                    return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started, attempts=requests)
                if decision is not CapDecision.RESERVED:
                    scope: Literal["user", "global"] = (
                        "user" if decision is CapDecision.USER_CAP else "global"
                    )
                    return self._error(
                        GatewayOutcome.CAP_REACHED, started, attempts=requests, cap_scope=scope
                    )
                remaining = deadline - self._clock()
                if remaining <= 0:
                    budget_gone = True
                    break
                requests += 1
                done = self._embed_attempt(
                    spec.name, number, min(spec.timeout_seconds, remaining), batch, task,
                    spec.dimensions, user_id, run_id,
                )  # fmt: skip
                if isinstance(done, EmbedOk):
                    vectors += done.vectors
                    tokens_in += done.tokens_in
                    break
                failure, transient = done
                failures.append(failure)
                if failure is ModelFailure.BAD_RESPONSE:
                    return self._error(GatewayOutcome.BAD_OUTPUT, started, attempts=requests)
                if not transient:
                    return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started, attempts=requests)
            else:
                return self._error(
                    self._exhausted(failures, budget_gone), started, attempts=requests
                )
            if len(vectors) != first + len(batch):  # the batch loop broke without a result
                return self._error(
                    self._exhausted(failures, budget_gone), started, attempts=requests
                )
        return EmbedGatewayOk(
            vectors=vectors, model=spec.name, attempts=requests, tokens_in=tokens_in,
            duration_ms=self._ms(started),
        )  # fmt: skip

    def _embed_attempt(
        self,
        model: str,
        number: int,
        timeout: float,
        batch: list[str],
        task: EmbedTask,
        dimensions: int,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
    ) -> EmbedOk | tuple[ModelFailure, bool]:
        """One embedding request and its ai_calls row. A failure comes back with whether trying the
        same model again could help."""
        assert self._client is not None  # noqa: S101  # narrows the type; _embed checked it
        began = self._clock()
        try:
            result = self._client.embed(
                model=model, texts=batch, task_type=task.value, dimensions=dimensions,
                timeout=timeout,
            )  # fmt: skip
        except Exception:  # noqa: BLE001  # a client that raises is just another failure
            result = ClientFailure(kind=ModelFailure.OTHER)
        failure_kind: FailureKind | None = None
        tokens_in = 0
        outcome: EmbedOk | tuple[ModelFailure, bool]
        if isinstance(result, ClientFailure):
            status = _CALL_STATUS[result.kind]
            failure_kind = result.detail or _DEFAULT_KIND.get(result.kind)
            outcome = (result.kind, failure_kind not in _NOT_TRANSIENT)
        elif isinstance(result, EmbedOk) and self._vectors_fit(result, len(batch), dimensions):
            status, tokens_in, outcome = AiCallStatus.OK, result.tokens_in, result
        else:  # garbage, or a wrong count or size that the client did not catch
            status, failure_kind = AiCallStatus.ERROR, FailureKind.BAD_JSON
            outcome = (ModelFailure.BAD_RESPONSE, False)
        cost = (
            Decimal(tokens_in) * Decimal(str(self._limits.embed_usd_per_million_tokens)) / 1_000_000
        ).quantize(Decimal("0.000001"))
        latency = self._ms(began)
        try:
            record_attempt(
                self._sessions, user_id=user_id, run_id=run_id, purpose=AiPurpose.EMBED,
                model=model, attempt=number, status=status, tokens_in=tokens_in, tokens_out=0,
                latency_ms=latency, failure_kind=failure_kind, est_cost_usd=cost,
            )  # fmt: skip
        except Exception:  # noqa: BLE001
            logger.error("ai bookkeeping failed code=%s", "AI_RECORD_FAILED")
        logger.info(
            "ai model=%s outcome=%s ms=%d tokens_in=%d tokens_out=0 run=%s",
            model, status.value, latency, tokens_in, run_id or "-",
        )  # fmt: skip
        return outcome

    @staticmethod
    def _vectors_fit(result: EmbedOk, count: int, dimensions: int) -> bool:
        return len(result.vectors) == count and all(len(v) == dimensions for v in result.vectors)

    def _ms(self, since: float) -> int:
        return max(0, int((self._clock() - since) * 1000))

    def _error(
        self,
        outcome: GatewayOutcome,
        started: float,
        *,
        attempts: int = 0,
        cap_scope: Literal["user", "global"] | None = None,
    ) -> GatewayError:
        return GatewayError(
            outcome=outcome, attempts=attempts, cap_scope=cap_scope, duration_ms=self._ms(started)
        )

    def _ask(
        self,
        prompt: str,
        system: str | None,
        purpose: AiPurpose,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        response_model: type[BaseModel] | None,
        job_class: JobClass,
        started: float,
    ) -> GatewayResult:
        if not isinstance(prompt, str) or (system is not None and not isinstance(system, str)):
            return self._error(GatewayOutcome.BAD_INPUT, started)
        if len(prompt) + len(system or "") > self._limits.max_prompt_chars:
            return self._error(GatewayOutcome.BAD_INPUT, started)
        key = self._api_key
        if key is None or not key.get_secret_value().strip():
            return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started)
        if self._chains is None or self._client is None:
            return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started)
        chain = self._chains.for_class(job_class)

        schema = response_model.model_json_schema() if response_model is not None else None
        deadline = started + chain.total_budget_seconds
        failures: list[ModelFailure] = []
        attempts = 0
        budget_gone = False
        for number, spec in enumerate(chain.chain, start=1):
            if self._clock() >= deadline:
                budget_gone = True
                break
            decision = reserve_call(
                self._sessions,
                user_id=user_id,
                day=self._today(),
                per_user=self._limits.daily_calls_per_user,
                per_day=self._limits.daily_calls_global,
            )
            if decision is CapDecision.UNAVAILABLE:
                return self._error(GatewayOutcome.MODEL_UNAVAILABLE, started, attempts=attempts)
            if decision is not CapDecision.RESERVED:
                scope: Literal["user", "global"] = (
                    "user" if decision is CapDecision.USER_CAP else "global"
                )
                return self._error(
                    GatewayOutcome.CAP_REACHED, started, attempts=attempts, cap_scope=scope
                )
            remaining = deadline - self._clock()
            if remaining <= 0:
                budget_gone = True
                break
            attempts += 1
            finished = self._attempt(
                spec, number, min(spec.timeout_seconds, remaining), prompt, system, schema,
                purpose, user_id, run_id, response_model,
            )  # fmt: skip
            if isinstance(finished, ModelFailure):
                failures.append(finished)
                if finished is ModelFailure.BAD_RESPONSE:
                    return self._error(GatewayOutcome.BAD_OUTPUT, started, attempts=attempts)
                continue
            if finished is None:
                return self._error(GatewayOutcome.BAD_OUTPUT, started, attempts=attempts)
            text, parsed, tokens_in, tokens_out = finished
            return GatewayOk(
                text=text, parsed=parsed, model=spec.name, attempts=attempts,
                tokens_in=tokens_in, tokens_out=tokens_out, duration_ms=self._ms(started),
            )  # fmt: skip
        return self._error(self._exhausted(failures, budget_gone), started, attempts=attempts)

    @staticmethod
    def _exhausted(failures: list[ModelFailure], budget_gone: bool) -> GatewayOutcome:
        if budget_gone or ModelFailure.TIMEOUT in failures:
            return GatewayOutcome.TIMEOUT
        if failures and all(f is ModelFailure.RATE_LIMITED for f in failures):
            return GatewayOutcome.BUSY
        return GatewayOutcome.MODEL_UNAVAILABLE

    def _attempt(
        self,
        spec: ModelSpec,
        number: int,
        timeout: float,
        prompt: str,
        system: str | None,
        schema: dict[str, object] | None,
        purpose: AiPurpose,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        response_model: type[BaseModel] | None,
    ) -> ModelFailure | tuple[str, BaseModel | None, int, int] | None:
        """One request. Returns a ModelFailure to move on, None for unusable output (stop), or
        (text, parsed, tokens_in, tokens_out). Always writes the ai_calls row."""
        assert self._client is not None  # noqa: S101  # narrows the type; _ask checked it
        began = self._clock()
        try:
            result = self._client.generate(
                model=spec.name, prompt=prompt, system=system, response_schema=schema,
                max_output_tokens=spec.max_output_tokens, thinking_budget=spec.thinking_budget,
                timeout=timeout, thinking_level=spec.thinking_level,
            )  # fmt: skip
        except Exception:  # noqa: BLE001  # a client that raises is just another failure
            result = ClientFailure(kind=ModelFailure.OTHER)
        outcome: ModelFailure | tuple[str, BaseModel | None, int, int] | None
        tokens_in = tokens_out = 0
        failure_kind: FailureKind | None = None
        if isinstance(result, ClientFailure):
            outcome, status = result.kind, _CALL_STATUS[result.kind]
            failure_kind = result.detail or _DEFAULT_KIND.get(result.kind)
        elif isinstance(result, ClientOk):
            tokens_in, tokens_out = result.tokens_in, result.tokens_out
            parsed = self._usable(result.text, response_model)
            if parsed is None:
                outcome, status = None, AiCallStatus.ERROR
            else:
                outcome, status = (result.text, parsed[0], tokens_in, tokens_out), AiCallStatus.OK
        else:  # not a ClientResult at all: garbage from the client
            outcome, status = None, AiCallStatus.ERROR
        self._record(
            spec,
            number,
            purpose,
            user_id,
            run_id,
            status,
            tokens_in,
            tokens_out,
            began,
            failure_kind,
        )
        return outcome

    @staticmethod
    def _usable(
        text: str, response_model: type[BaseModel] | None
    ) -> tuple[BaseModel | None] | None:
        """(parsed,) when the text is usable, else None. Strict: no cleaning of the model output."""
        if not text.strip():
            return None
        if response_model is None:
            return (None,)
        try:
            return (response_model.model_validate_json(text),)
        except ValueError:
            return None

    def _record(
        self,
        spec: ModelSpec,
        number: int,
        purpose: AiPurpose,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        status: AiCallStatus,
        tokens_in: int,
        tokens_out: int,
        began: float,
        failure_kind: FailureKind | None = None,
    ) -> None:
        """Bookkeeping must never change the result or raise: log a code and move on."""
        latency = self._ms(began)
        try:
            record_attempt(
                self._sessions, user_id=user_id, run_id=run_id, purpose=purpose,
                model=spec.name, attempt=number, status=status, tokens_in=tokens_in,
                tokens_out=tokens_out, latency_ms=latency, failure_kind=failure_kind,
            )  # fmt: skip
        except Exception:  # noqa: BLE001
            logger.error("ai bookkeeping failed code=%s", "AI_RECORD_FAILED")
        logger.info(
            "ai model=%s outcome=%s ms=%d tokens_in=%d tokens_out=%d run=%s",
            spec.name, status.value, latency, tokens_in, tokens_out, run_id or "-",
        )  # fmt: skip


def build_gateway(settings: Settings, session_factory: SessionFactory) -> Gateway:
    """The production gateway. Under app_env=test the real client is never built, so a test that
    forgets to inject a fake gets MODEL_UNAVAILABLE instead of a network call. A missing or broken
    models.toml also gives MODEL_UNAVAILABLE, not a crash."""
    try:
        chains: ModelChains | None = load_model_chains()
    except Exception:  # noqa: BLE001
        logger.error("ai config failed code=%s", "AI_CONFIG_INVALID")
        chains = None
    client: ModelClient | None = None
    key = settings.gemini_api_key
    if settings.app_env != "test" and key is not None and key.get_secret_value().strip():
        from app.ai.real_client import GeminiRestClient  # noqa: PLC0415  # kept out of test paths

        client = GeminiRestClient(key)
    return Gateway(
        api_key=key,
        chains=chains,
        limits=settings.limits,
        session_factory=session_factory,
        client=client,
    )
