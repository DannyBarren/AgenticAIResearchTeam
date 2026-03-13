"""Security and cost-control for crew runs: rate limiting, cost guardrail, logging.
Invisible until limits or cost threshold are hit.

Copyright Daniel Lee Barren 2026
"""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
SECURITY_LOG_MAX_COST_USD = 2.0
SERPER_LIMIT = 15
OPENAI_CALL_LIMIT = 30


class SecurityLimitError(Exception):
    """Raised when rate or cost limit is exceeded; human approval required."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# Approximate cost per 1k tokens for OpenAI gpt-4o-mini (conservative)
OPENAI_INPUT_COST_PER_1K = 0.0025
OPENAI_OUTPUT_COST_PER_1K = 0.01


class SecurityState:
    """Shared state for rate limits and cost; thread-safe."""

    _lock = threading.Lock()
    serper_calls: int = 0
    llm_calls: int = 0
    estimated_tokens_input: int = 0
    estimated_tokens_output: int = 0
    cost_limit_hit: bool = False
    serper_limit_hit: bool = False
    llm_limit_hit: bool = False

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls.serper_calls = 0
            cls.llm_calls = 0
            cls.estimated_tokens_input = 0
            cls.estimated_tokens_output = 0
            cls.cost_limit_hit = False
            cls.serper_limit_hit = False
            cls.llm_limit_hit = False

    @classmethod
    def increment_serper(cls) -> bool:
        """Increment search count; return True if under limit, False if limit hit."""
        with cls._lock:
            cls.serper_calls += 1
            if cls.serper_calls > SERPER_LIMIT:
                cls.serper_limit_hit = True
                return False
            return True

    @classmethod
    def increment_llm(cls, input_tokens: int = 3000, output_tokens: int = 1500) -> bool:
        """Increment LLM call count and token estimate; return False if limit or cost hit."""
        with cls._lock:
            cls.llm_calls += 1
            cls.estimated_tokens_input += input_tokens
            cls.estimated_tokens_output += output_tokens
            if cls.llm_calls > OPENAI_CALL_LIMIT:
                cls.llm_limit_hit = True
            cost = (
                cls.estimated_tokens_input / 1000 * OPENAI_INPUT_COST_PER_1K
                + cls.estimated_tokens_output / 1000 * OPENAI_OUTPUT_COST_PER_1K
            )
            if cost > SECURITY_LOG_MAX_COST_USD:
                cls.cost_limit_hit = True
            return not (cls.llm_limit_hit or cls.cost_limit_hit)

    @classmethod
    def estimated_cost_usd(cls) -> float:
        with cls._lock:
            return (
                cls.estimated_tokens_input / 1000 * OPENAI_INPUT_COST_PER_1K
                + cls.estimated_tokens_output / 1000 * OPENAI_OUTPUT_COST_PER_1K
            )

    @classmethod
    def should_stop(cls) -> tuple[bool, str]:
        """Return (True, reason) if run should stop."""
        with cls._lock:
            if cls.cost_limit_hit:
                return True, (
                    f"Estimated cost ${cls.estimated_cost_usd():.2f} exceeds "
                    f"${SECURITY_LOG_MAX_COST_USD:.2f}. Human approval required."
                )
            if cls.llm_limit_hit:
                return True, (
                    f"LLM call limit ({OPENAI_CALL_LIMIT}) exceeded. "
                    "Human approval required to continue."
                )
            if cls.serper_limit_hit:
                return True, (
                    f"Search limit ({SERPER_LIMIT}) exceeded. "
                    "Human approval required to continue."
                )
        return False, ""


def describe_security_limits() -> str:
    """Return a human-readable summary of current security limits for each API."""
    return (
        "Current security limits per run:\n"
        "\n"
        "OpenAI LLM (gpt-4o-mini):\n"
        f"- Max LLM calls: {OPENAI_CALL_LIMIT}\n"
        f"- Approximate cost cap: ${SECURITY_LOG_MAX_COST_USD:.2f} (estimated from token usage)\n"
        "\n"
        "Search APIs (SerperDevTool and WebsiteSearchTool):\n"
        f"- Max search calls: {SERPER_LIMIT}\n"
    )


def _log_security(line: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = LOG_DIR / f"security_log_{date_str}.txt"
    ts = datetime.now().isoformat()
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{ts} | {line}\n")
    except OSError:
        pass


def create_rate_limited_serper():
    """Return a SerperDevTool instance that enforces SERPER_LIMIT via a wrapped _run."""
    from crewai_tools import SerperDevTool

    base = SerperDevTool()
    original_run = base._run

    def wrapped_run(*args, **kwargs):
        if not SecurityState.increment_serper():
            _log_security(f"RATE_LIMIT serper_calls={SecurityState.serper_calls} (max {SERPER_LIMIT})")
            return (
                f"[Security] Search limit reached ({SERPER_LIMIT} per run). "
                "No more Serper searches this run. Use existing context or ask for human approval."
            )
        q = kwargs.get("search_query", "") or (args[0] if args else "")
        _log_security(f"TOOL SerperDevTool query={str(q)[:80]!r}")
        return original_run(*args, **kwargs)

    base._run = wrapped_run
    return base


def create_rate_limited_website_search():
    """Return a WebsiteSearchTool instance that enforces the same search limit."""
    from generic_consultant_crew.tools.docs_tools import get_website_search_tool_base

    base = get_website_search_tool_base()
    original_run = base._run

    def wrapped_run(*args, **kwargs):
        if not SecurityState.increment_serper():
            _log_security(f"RATE_LIMIT website_search (count={SecurityState.serper_calls}, max {SERPER_LIMIT})")
            return (
                f"[Security] Search limit reached ({SERPER_LIMIT} per run). "
                "No more searches this run."
            )
        _log_security("TOOL WebsiteSearchTool")
        return original_run(*args, **kwargs)

    base._run = wrapped_run
    return base


# Wrapped tool instances (created on first use to avoid import cycles)
_rate_limited_serper = None
_rate_limited_website_search = None


def get_rate_limited_serper():
    global _rate_limited_serper
    if _rate_limited_serper is None:
        _rate_limited_serper = create_rate_limited_serper()
    return _rate_limited_serper


def get_rate_limited_website_search():
    global _rate_limited_website_search
    if _rate_limited_website_search is None:
        _rate_limited_website_search = create_rate_limited_website_search()
    return _rate_limited_website_search


def setup_security_listener():
    """Register event listener for tool usage and LLM calls; log and enforce limits."""
    from crewai.events import (
        BaseEventListener,
        ToolUsageStartedEvent,
        ToolUsageFinishedEvent,
        LLMCallCompletedEvent,
        crewai_event_bus,
    )

    class SecurityEventListener(BaseEventListener):
        def setup_listeners(self, bus):
            @bus.on(ToolUsageStartedEvent)
            def on_tool_started(source, event):
                try:
                    name = getattr(event, "tool_name", None) or getattr(event, "name", "?")
                    _log_security(f"TOOL_START {name}")
                except Exception:
                    pass

            @bus.on(ToolUsageFinishedEvent)
            def on_tool_finished(source, event):
                try:
                    name = getattr(event, "tool_name", None) or getattr(event, "name", "?")
                    _log_security(f"TOOL_FINISH {name}")
                except Exception:
                    pass

            @bus.on(LLMCallCompletedEvent)
            def on_llm_completed(source, event):
                try:
                    inp = getattr(event, "input_tokens", None) or getattr(event, "prompt_tokens", 3000)
                    out = getattr(event, "output_tokens", None) or getattr(event, "completion_tokens", 1500)
                    SecurityState.increment_llm(inp, out)
                    _log_security(
                        f"LLM_CALL llm_calls={SecurityState.llm_calls} "
                        f"est_cost=${SecurityState.estimated_cost_usd():.4f}"
                    )
                    stop, reason = SecurityState.should_stop()
                    if stop:
                        _log_security(f"SECURITY_STOP {reason}")
                        raise SecurityLimitError(reason)
                except SecurityLimitError:
                    raise
                except Exception:
                    SecurityState.increment_llm(3000, 1500)
                    _log_security(f"LLM_CALL llm_calls={SecurityState.llm_calls}")
                    stop, reason = SecurityState.should_stop()
                    if stop:
                        raise SecurityLimitError(reason)

    listener = SecurityEventListener()
    listener.setup_listeners(crewai_event_bus)
    return listener

