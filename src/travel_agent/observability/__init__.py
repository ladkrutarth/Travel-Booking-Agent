"""Cost tracking and LangSmith/tracing hooks."""

from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

from travel_agent.config import get_settings
from travel_agent.observability.logging import get_logger, log_event

logger = get_logger(__name__)

# Rough USD per 1K tokens for cost accounting (approximate; override via env if needed)
_MODEL_RATES = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}


@dataclass
class CostTracker:
    trip_id: str
    max_cost_usd: float
    spent_usd: float = 0.0
    steps: int = 0
    max_steps: int = 12
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def add_tokens(self, model: str, input_tokens: int, output_tokens: int) -> float:
        rates = _MODEL_RATES.get(model, _MODEL_RATES["gpt-4o"])
        cost = (input_tokens / 1000.0) * rates["input"] + (output_tokens / 1000.0) * rates[
            "output"
        ]
        self.spent_usd += cost
        return cost

    def add_flat(self, amount: float) -> None:
        self.spent_usd += amount

    def bump_step(self) -> None:
        self.steps += 1

    def within_limits(self) -> bool:
        return self.spent_usd <= self.max_cost_usd and self.steps <= self.max_steps

    def assert_within_limits(self) -> None:
        if self.steps > self.max_steps:
            raise RuntimeError(f"step limit exceeded: {self.steps}/{self.max_steps}")
        if self.spent_usd > self.max_cost_usd:
            raise RuntimeError(
                f"cost cap exceeded: ${self.spent_usd:.4f} > ${self.max_cost_usd:.4f}"
            )


def configure_tracing() -> None:
    settings = get_settings()
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        log_event(logger, "LangSmith tracing enabled", event="tracing_enabled")
    else:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")


@contextmanager
def timed_span(
    name: str, *, trip_id: Optional[str] = None, **attrs: Any
) -> Generator[Dict[str, Any], None, None]:
    start = time.perf_counter()
    span: Dict[str, Any] = {"name": name, **attrs}
    try:
        yield span
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        span["latency_ms"] = latency_ms
        log_event(
            logger,
            f"span:{name}",
            trip_id=trip_id,
            event="span",
            latency_ms=round(latency_ms, 2),
            **{k: v for k, v in attrs.items() if k != "latency_ms"},
        )
