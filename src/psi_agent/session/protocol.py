"""Types shared across the session layer — data models and serialisation.

The wire-format types and every shared protocol constant now live in
``psi_agent.protocol`` (the cross-component owner) and are re-exported here so
existing ``psi_agent.session.protocol`` imports keep working.  Prefer importing
shared names from ``psi_agent.protocol`` in new code; this module's own
contribution is the Session-only types below.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from psi_agent.protocol import (
    FINISH_REASON_COMPACTION_NEEDED,
    FINISH_REASON_ERROR,
    FINISH_REASON_LENGTH,
    FINISH_REASON_STOP,
    FINISH_REASON_TOOL_CALLS,
    REASONING_KIND_THINKING,
    REASONING_KIND_TOOL_CALL,
    REASONING_KIND_TOOL_RESULT,
    ChatCompletionChunk,
    DeltaMessage,
    StreamChoice,
    is_auxiliary_finish,
    is_terminal_finish,
)

__all__ = [
    "DEFAULT_MAX_TOOL_ROUNDS",
    "DEFAULT_SOFT_TOOL_ROUNDS",
    "S2_CYCLE_MIN_REPEATS",
    "S2_CYCLE_MAX_LENGTH",
    "S3_WINDOW_ROUNDS",
    "DEFAULT_CHECKPOINT_TURNS",
    "STALL_CHECKPOINT",
    "SOFT_LIMIT_CHECKPOINT",
    "FINISH_REASON_COMPACTION_NEEDED",
    "FINISH_REASON_ERROR",
    "FINISH_REASON_LENGTH",
    "FINISH_REASON_STOP",
    "FINISH_REASON_TOOL_CALLS",
    "LENGTH_TRUNCATION_PLACEHOLDER",
    "MAX_CONSECUTIVE_LENGTH_TRUNCATIONS",
    "MAX_ROUNDS_NOTICE",
    "REASONING_KIND_THINKING",
    "REASONING_KIND_TOOL_CALL",
    "REASONING_KIND_TOOL_RESULT",
    "AgentChunk",
    "AgentError",
    "AgentRunResult",
    "AgentRunStatus",
    "AgentStopCause",
    "AiDelta",
    "ChatCompletionChunk",
    "DeltaMessage",
    "StreamChoice",
    "is_auxiliary_finish",
    "is_terminal_finish",
]


DEFAULT_SOFT_TOOL_ROUNDS = 128
"""Soft round ceiling: where the runtime starts asking the model to self-audit.

At this round the loop appends a progress checkpoint to the next model request.
The model should continue only when it can name a concrete primary-metric
improvement or a completion-counter increase against its first-deliverable
contract; otherwise it should finalize the best judgeable state.  The soft
limit is *not* a hard stop — it opens a bounded extension window up to
``DEFAULT_MAX_TOOL_ROUNDS``.
"""

DEFAULT_MAX_TOOL_ROUNDS = 160
"""Hard ceiling on agent-loop rounds per turn.  Unconditional stop.

The 32 rounds between soft and hard are a bounded extension for long tasks that
still show measurable progress, not a license to repeat the same work.  Both
limits count *model rounds* (one AI request per round, possibly several tool
calls).  Single source of truth for ``Session``, ``SessionAgent.__init__`` and
``SessionAgent.create``.
"""

LENGTH_TRUNCATION_PLACEHOLDER = (
    "[上一轮输出达到长度上限被截断；本轮的 reasoning_content 是已产生的推理内容]"
)
"""Non-empty ``content`` written alongside a truncated round's reasoning.

Measured against the live provider endpoint: an assistant message with an empty
``content`` and only ``reasoning_content`` is treated as **non-existent** -- the
model re-plans the task from scratch instead of continuing (sentinel probe: it
denied the reasoning content existed, twice).  Adding ``content`` + the same
``reasoning_content`` made the model see and quote it.  So the placeholder is
load-bearing, not cosmetic: without it the resumable-truncation path saves
reasoning that the provider will never read.
"""

MAX_CONSECUTIVE_LENGTH_TRUNCATIONS = 3
"""How many *consecutive* ``finish_reason="length"`` rounds a turn will resume.

A truncation is resumable, so the loop saves the partial assistant output and
issues the next round instead of dropping the round.  The streak is what is
bounded, not lifetime volume: any terminal reason other than ``length`` resets
it, so an isolated truncation that recovers costs nothing.  Three consecutive
truncations means continuation is not making progress -- the turn stops and
keeps whatever was produced.
"""

S2_CYCLE_MIN_REPEATS = 3
"""How many times a tool-name cycle must repeat (with unchanged result
signatures) before it counts as an S2 loop."""

S2_CYCLE_MAX_LENGTH = 4
"""Longest tool-name cycle the S2 detector considers, in tools."""

S3_WINDOW_ROUNDS = 6
"""Sliding window (in model rounds) for S3 execution-novelty detection.

S3 fires when the last ``S3_WINDOW_ROUNDS`` executed tool calls produced no
``(tool_name, normalized_args, result_signature)`` triple that had not already
been seen before the window opened."""

DEFAULT_CHECKPOINT_TURNS = (32, 64, 96, 112, 120)
"""Model-round numbers in the *normal* window that get a deterministic
progress self-audit.  Injected into that round as a trailing message only,
never into history, so the model is steered toward convergence early
instead of first being asked at the soft limit.
"""
"""Sliding window (in model rounds) for S3 execution-novelty detection.

S3 fires when the last ``S3_WINDOW_ROUNDS`` executed tool calls produced no
``(tool_name, normalized_args, result_signature)`` triple that had not already
been seen before the window opened."""

STALL_CHECKPOINT = (
    "【进度自检】检测到你可能在空转（重复动作 / 循环 / 连续无新执行状态）。"
    "请先在心里自检下面六点，然后**立刻继续执行下一步**（本轮就要给出工具调用，不要只回文字）：\n"
    "1. 剩余 gap = ？（目标 - 当前），证据等级 Direct / Mirror / Inferred？\n"
    "2. 最近 3 轮 gap 在缩小吗，还是只是「做了新动作」？\n"
    "3. 你现在这个动作闭合哪个 gap？预期改善多少？\n"
    "4. 是否已进入 Endgame（接近目标 / 完成比例高 / 改善趋缓）？\n"
    "5. 当前 blocker 是否来自官方验收？不来自就降级。\n"
    "6. 下一步：闭合 gap / 换策略 / 收尾？"
)

SOFT_LIMIT_CHECKPOINT = (
    "【软上限自检】已经跑了 {rounds} 轮。"
    "只有当你能量化说出「主指标改善」或「完成计数增加」时才继续；"
    "否则立即收尾，交付当前最好的成果。"
)
MAX_ROUNDS_NOTICE = (
    "\n\n[已达到单轮工具调用上限, 停在这里]"
    "我连续调用了 {rounds} 轮工具还没得出结论, 先停下来避免空转。"
    "可以让我接着查, 或者把问题拆小一点、说得更具体一些。"
)
"""User-facing text appended when the round limit stops a turn.

Written for the person in the chat, not for a log reader: the bare
``[Max tool rounds reached]`` this replaces was an untranslated developer token
that arrived glued to whatever interstitial narration the model had produced
("让我再查一下。[Max tool rounds reached]"), so a Feishu user saw a half-finished
reply with a bracketed English string and no way to tell a round-limit stop from
a crash.  It states what happened, why, and what to do next, and carries the
round count so the log line and the chat agree on the same number.

Leading blank line separates it from the model's own last words; the bracketed
prefix stays so operators grepping histories keep a stable marker.
"""


class AgentError(Exception):
    """Unrecoverable error from the agent loop.

    Raised by ``SessionAgent.run()`` when the AI backend returns a non-200
    status or a stream with ``finish_reason="error"``.

    Caught by ``ChannelAdapter.write()``, which serialises it as a
    ``ChatCompletionChunk`` with ``finish_reason="error"`` for the channel
    client.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AgentRunStatus(StrEnum):
    """Whether a normally-returning run produced a *complete* answer.

    Only describes normal return.  Execution failure raises ``AgentError``
    instead and yields no result at all — the two are mutually exclusive.
    """

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"


class AgentStopCause(StrEnum):
    """Why the agent runtime stopped, expressed in *runtime* terms.

    Distinct from ``model_finish_reason`` (the model's raw diagnostic string):
    several finish reasons — and the absence of one — collapse into a single
    runtime cause, and ``AGENT_TURN_LIMIT`` has no model-side equivalent at all.
    """

    MODEL_COMPLETED = "model_completed"
    """Model finished on its own with ``stop``."""
    MODEL_STOPPED = "model_stopped"
    """Model stopped for its own reason other than ``stop``, and the round was
    not truncated (e.g. an unknown finish reason)."""
    MODEL_TRUNCATED = "model_truncated"
    """The reply was cut off by the provider's output-token ceiling
    (``finish_reason="length"``) and the bounded continuation budget ran out.
    Distinct from ``MODEL_STOPPED`` so triage can tell "the model chose to stop"
    from "the provider cut it off"."""
    AGENT_TURN_LIMIT = "agent_turn_limit"
    """Agent loop hit ``max_tool_rounds``.  The limit counts *rounds*, and one
    round may carry several tool calls — hence "turn limit", not "tool limit"."""
    INVALID_MODEL_STREAM = "invalid_model_stream"
    """Stream ended without ever reporting a finish reason."""


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Immutable terminal state of one fully-consumed ``SessionAgent`` run.

    Available as ``AgentRun.result`` once the chunk stream is exhausted; stays
    ``None`` while the run is in flight, and is never set when the run raises
    ``AgentError`` (failure is signalled by the exception, not by a result).
    """

    status: AgentRunStatus
    stop_cause: AgentStopCause
    model_finish_reason: str | None
    """The model's raw ``finish_reason``, kept verbatim for logs and triage —
    including reasons this code does not know about.  ``None`` when the stream
    never reported one."""
    model_turns: int
    """How many model requests this run issued (rounds of the agent loop)."""

    @property
    def is_complete(self) -> bool:
        return self.status is AgentRunStatus.COMPLETED


@dataclass
class AgentChunk:
    """Semantic output of ``SessionAgent.run()`` — content and/or reasoning.

    The agent loop yields these to ``ChannelAdapter``, which converts them to
    ``ChatCompletionChunk`` for SSE output.  Contains no protocol fields
    (no ``id``, ``choices``, ``finish_reason``, etc.).

    ``kind`` is provenance for ``reasoning`` only (``thinking`` / ``tool_call`` /
    ``tool_result``). Tool progress remains in the ``reasoning`` slot on purpose
    (compressed process stream for OpenAI-shaped Session↔AI reuse); UI filters
    by ``kind`` instead of splitting the wire field.
    """

    content: str | None = None
    reasoning: str | None = None
    kind: str | None = None


@dataclass
class AiDelta:
    """Internal stream element from ``AiClient.stream()``.

    Consumed by ``SessionAgent.run()`` to drive the agent loop.  Contains
    SSE-level fields (``tool_calls`` as partial dicts, ``finish_reason``)
    that the agent loop accumulates and acts on.  ``compaction_needed``
    signals that the AI layer detected a token-threshold exceed.

    Optional ``kind`` is passed through when the upstream delta already tags
    reasoning provenance; otherwise Session defaults model ``reasoning`` to
    ``thinking``.

    Never exposed to the Channel side.
    """

    content: str | None = None
    reasoning: str | None = None
    kind: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None
    compaction_needed: bool = False
    prompt_tokens: int = 0
    """Upstream-reported prompt tokens carried by the compaction signal (0 = unknown)."""
    compaction_threshold: int = 0
    """The threshold the signal was raised against (0 = unknown)."""
    usage_prompt_tokens: int = 0
    """Prompt tokens from the stream's own ``usage`` chunk (0 = not reported yet).

    Distinct from ``prompt_tokens`` on purpose: that one rides the compaction
    signal and therefore only appears once the threshold is already exceeded,
    which is far too late to calibrate anything.  This one arrives on every
    successful turn (the AI layer forces ``stream_options.include_usage``), and
    is what ``RequestAssembler.calibrate`` divides into the character count we
    measured for that same request.
    """
