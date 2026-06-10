"""Failing-first tests for data_svc.market_selection (pure filter rules).

Fixtures mirror the live Kalshi /markets shape: prices are dollar STRINGS
(``*_dollars``), volume/OI are ``*_fp`` strings. evaluate() converts
dollars -> cents internally; spreads are computed in cents.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from data_svc.market_selection import (
    SelectionConfig,
    SelectionResult,
    SkipReason,
    Tier,
    evaluate,
    series_of,
    summarize_selected_by_series,
    summarize_skips,
)


def _config(**overrides: Any) -> SelectionConfig:
    base: dict[str, Any] = {
        "named_series_prefixes": frozenset({"KXFED", "KXPRES", "KXECON"}),
        "tight_max_spread_cents": Decimal("2"),
        "tight_min_volume_24h": 50,
        "default_max_spread_cents": Decimal("5"),
        "default_min_volume_24h": 1000,
    }
    base.update(overrides)
    return SelectionConfig(**base)


def _market(ticker: str = "KXFED-25DEC-T3.00", **overrides: Any) -> dict[str, Any]:
    """Default: 1c spread (0.47/0.48), volume 5000 — passes the tight tier."""
    base: dict[str, Any] = {
        "ticker": ticker,
        "yes_bid_dollars": "0.4700",
        "yes_ask_dollars": "0.4800",
        "no_bid_dollars": "0.5200",
        "no_ask_dollars": "0.5300",
        "volume_fp": "5000.00",
        "open_interest_fp": "1200.00",
        "last_price_dollars": "0.4750",
    }
    base.update(overrides)
    return base


# --- series extraction -------------------------------------------------

def test_series_of_extracts_prefix_before_first_dash() -> None:
    assert series_of("KXFED-25DEC-T3.00") == "KXFED"
    assert series_of("KXPRES-2028-DEM") == "KXPRES"


# --- tier resolution ---------------------------------------------------

def test_evaluate_assigns_tight_tier_when_ticker_is_named_series() -> None:
    assert evaluate(_market(ticker="KXFED-25DEC-T3.00"), _config()).tier == Tier.TIGHT


def test_evaluate_assigns_default_tier_when_ticker_not_named_series() -> None:
    assert evaluate(_market(ticker="KXNBA-LAL-WIN"), _config()).tier == Tier.DEFAULT


# --- pass cases --------------------------------------------------------

def test_evaluate_passes_when_tight_market_meets_tight_thresholds() -> None:
    result = evaluate(_market(ticker="KXFED-25DEC-T3.00"), _config())
    assert result.passed is True
    assert result.reason is None
    assert result.tier == Tier.TIGHT


def test_evaluate_passes_when_default_market_meets_default_thresholds() -> None:
    m = _market(
        ticker="KXNBA-LAL-WIN",
        yes_bid_dollars="0.4000",
        yes_ask_dollars="0.4400",  # 4c spread <= default 5c
        volume_fp="2000.00",  # >= default 1000
    )
    result = evaluate(m, _config())
    assert result.passed is True
    assert result.reason is None
    assert result.tier == Tier.DEFAULT


def test_evaluate_passes_sports_market_when_genuinely_liquid() -> None:
    """The explicit 'open to sports' intent: a liquid sports market must
    not be filtered out just for being a sports ticker."""
    m = _market(
        ticker="KXNFL-SB-KC",
        yes_bid_dollars="0.5000",
        yes_ask_dollars="0.5300",  # 3c spread
        volume_fp="50000.00",
    )
    result = evaluate(m, _config())
    assert result.passed is True, "a genuinely liquid sports market must pass"
    assert result.tier == Tier.DEFAULT


# --- skip reasons ------------------------------------------------------

def test_evaluate_skips_no_book_when_any_quote_missing() -> None:
    m = _market()
    del m["no_ask_dollars"]
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.NO_BOOK


def test_evaluate_skips_no_book_when_any_quote_zero() -> None:
    result = evaluate(_market(yes_bid_dollars="0.0000"), _config())
    assert result.passed is False
    assert result.reason == SkipReason.NO_BOOK


def test_evaluate_skips_spread_too_wide_when_tight_tier_exceeds_cap() -> None:
    m = _market(
        ticker="KXFED-25DEC-T3.00",
        yes_bid_dollars="0.4000",
        yes_ask_dollars="0.4400",  # 4c spread > tight 2c
    )
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.SPREAD_TOO_WIDE
    assert result.tier == Tier.TIGHT


def test_evaluate_skips_spread_too_wide_when_default_tier_exceeds_cap() -> None:
    m = _market(
        ticker="KXNBA-LAL-WIN",
        yes_bid_dollars="0.4000",
        yes_ask_dollars="0.4800",  # 8c spread > default 5c
        volume_fp="2000.00",
    )
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.SPREAD_TOO_WIDE
    assert result.tier == Tier.DEFAULT


def test_evaluate_skips_volume_too_low_when_tight_tier_below_floor() -> None:
    result = evaluate(_market(ticker="KXFED-25DEC-T3.00", volume_fp="10.00"), _config())
    assert result.passed is False
    assert result.reason == SkipReason.VOLUME_TOO_LOW


def test_evaluate_skips_volume_too_low_when_default_tier_below_floor() -> None:
    m = _market(
        ticker="KXNBA-LAL-WIN",
        yes_bid_dollars="0.4000",
        yes_ask_dollars="0.4400",
        volume_fp="500.00",  # < default 1000
    )
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.VOLUME_TOO_LOW


# --- cross-tier: same numbers, different verdict by tier ---------------

def test_evaluate_applies_tighter_spread_cap_to_tight_than_default() -> None:
    """4c spread: passes DEFAULT (cap 5c) but fails TIGHT (cap 2c)."""
    tight = _market(
        ticker="KXFED-X", yes_bid_dollars="0.4000", yes_ask_dollars="0.4400",
        volume_fp="5000.00",
    )
    deflt = _market(
        ticker="KXNBA-X", yes_bid_dollars="0.4000", yes_ask_dollars="0.4400",
        volume_fp="5000.00",
    )
    assert evaluate(tight, _config()).reason == SkipReason.SPREAD_TOO_WIDE
    assert evaluate(deflt, _config()).passed is True


def test_evaluate_applies_lower_volume_floor_to_tight_than_default() -> None:
    """Volume 100: passes TIGHT floor (50) but fails DEFAULT floor (1000)."""
    tight = _market(ticker="KXFED-X", volume_fp="100.00")
    deflt = _market(ticker="KXNBA-X", volume_fp="100.00")
    assert evaluate(tight, _config()).passed is True
    assert evaluate(deflt, _config()).reason == SkipReason.VOLUME_TOO_LOW


# --- precedence + tier-on-skip ----------------------------------------

def test_evaluate_reports_no_book_before_spread_when_both_fail() -> None:
    """A zero quote makes spread meaningless; NO_BOOK must win precedence."""
    m = _market(ticker="KXFED-X", yes_ask_dollars="0.0000")
    assert evaluate(m, _config()).reason == SkipReason.NO_BOOK


def test_evaluate_records_tier_even_when_skipped() -> None:
    m = _market(ticker="KXFED-X", volume_fp="1.00")  # skipped (too low), still tight
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.tier == Tier.TIGHT


# --- aggregation helpers ----------------------------------------------

def test_summarize_skips_counts_each_reason() -> None:
    results = [
        SelectionResult(passed=False, reason=SkipReason.NO_BOOK, tier=Tier.DEFAULT),
        SelectionResult(passed=False, reason=SkipReason.NO_BOOK, tier=Tier.TIGHT),
        SelectionResult(passed=False, reason=SkipReason.SPREAD_TOO_WIDE, tier=Tier.DEFAULT),
        SelectionResult(passed=True, reason=None, tier=Tier.TIGHT),
    ]
    counts = summarize_skips(results)
    assert counts[SkipReason.NO_BOOK] == 2
    assert counts[SkipReason.SPREAD_TOO_WIDE] == 1
    assert counts.get(SkipReason.VOLUME_TOO_LOW, 0) == 0


def test_summarize_selected_by_series_groups_named_and_other() -> None:
    tickers = ["KXFED-A", "KXFED-B", "KXPRES-A", "KXNBA-A", "KXNFL-B"]
    counts = summarize_selected_by_series(tickers, _config())
    assert counts["KXFED"] == 2
    assert counts["KXPRES"] == 1
    assert counts["other"] == 2
