"""Token usage and cost accounting types.

Cost computation lives here so both the agent runtime and the test suite
agree on the same formula.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# USD per million tokens. Pricing is per-model and changes; keep a single
# source of truth here. Add new models as we adopt them.
PRICING: dict[str, tuple[float, float]] = {
    # input, output (USD per million tokens)
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}

# Cached input tokens are billed at 10% of the regular input price.
CACHE_READ_DISCOUNT = 0.10
# Cache writes (creating the cache) are billed at 125% of regular input.
CACHE_WRITE_PREMIUM = 1.25


class TokenUsage(BaseModel):
    """Token counts and computed cost for a single LLM call."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    @property
    def cache_hit_ratio(self) -> float:
        total_input = self.input_tokens + self.cache_read_input_tokens
        if total_input == 0:
            return 0.0
        return self.cache_read_input_tokens / total_input

    @property
    def cost_usd(self) -> float:
        if self.model not in PRICING:
            return 0.0
        input_rate, output_rate = PRICING[self.model]
        cost = (
            self.input_tokens * input_rate
            + self.cache_read_input_tokens * input_rate * CACHE_READ_DISCOUNT
            + self.cache_creation_input_tokens * input_rate * CACHE_WRITE_PREMIUM
            + self.output_tokens * output_rate
        ) / 1_000_000
        return round(cost, 6)


class AgentRunResult(BaseModel):
    """Outcome of one agent run, returned by BaseAgent.run()."""

    text: str = Field(description="Final assistant text")
    usage: TokenUsage
    duration_ms: int = 0
