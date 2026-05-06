from shared.tracing import TokenUsage


def test_cost_zero_for_unknown_model() -> None:
    u = TokenUsage(model="unknown", input_tokens=1000, output_tokens=1000)
    assert u.cost_usd == 0.0


def test_cost_basic_opus() -> None:
    # 1000 input * $15/M = $0.015; 1000 output * $75/M = $0.075; total $0.09
    u = TokenUsage(model="claude-opus-4-7", input_tokens=1000, output_tokens=1000)
    assert u.cost_usd == 0.09


def test_cache_read_discounted() -> None:
    u = TokenUsage(
        model="claude-opus-4-7",
        input_tokens=0,
        cache_read_input_tokens=1000,
        output_tokens=0,
    )
    # 1000 * $15/M * 10% = $0.0015
    assert u.cost_usd == 0.0015


def test_cache_hit_ratio() -> None:
    u = TokenUsage(
        model="claude-opus-4-7",
        input_tokens=200,
        cache_read_input_tokens=800,
    )
    assert u.cache_hit_ratio == 0.8


def test_cache_hit_ratio_zero_when_no_input() -> None:
    u = TokenUsage(model="claude-opus-4-7")
    assert u.cache_hit_ratio == 0.0
