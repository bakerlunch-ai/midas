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

def test_evaluate_book_decision_ignores_missing_no_side() -> None:
    """Option X: NO is mirror algebra, never inspected. A missing NO field does
    not affect publishability (it is derived downstream); a missing YES field
    is missing data -> NO_BOOK."""
    missing_no = _market(ticker="KXFED-25DEC-T3.00")
    del missing_no["no_ask_dollars"]
    assert evaluate(missing_no, _config()).passed is True

    missing_yes = _market(ticker="KXFED-25DEC-T3.00")
    del missing_yes["yes_ask_dollars"]
    assert evaluate(missing_yes, _config()).reason == SkipReason.NO_BOOK


def test_evaluate_skips_no_book_when_book_is_dead() -> None:
    """A genuinely dead book (both yes sides zero) skips NO_BOOK. A single zero
    with a live opposite side is a publishable one-sided book — see
    test_evaluate_passes_one_sided_favorite."""
    result = evaluate(
        _market(yes_bid_dollars="0.0000", yes_ask_dollars="0.0000"), _config()
    )
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

def test_evaluate_reports_no_book_before_other_reasons_when_book_dead() -> None:
    """NO_BOOK has precedence: a dead book is skipped as NO_BOOK even when
    volume is also below floor."""
    m = _market(
        ticker="KXFED-X",
        yes_bid_dollars="0.0000",
        yes_ask_dollars="0.0000",
        volume_fp="1.00",
    )
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


# --- is_publishable_book: the shared book predicate (Lesson 5, OR semantics) --
# The book is two real numbers b=yes_bid, a=yes_ask (cents); NO is mirror
# algebra and is never inspected. Publishable iff at least one side carries a
# real (non-zero) quote; a missing side (None) is missing DATA, not a zero.
#
# NOTE (failing-first): is_publishable_book does not exist yet. The import is
# LOCAL to each test so the expected ImportError is isolated to these 7 cases
# and does not break collection of the rest of the module. It moves to the
# top-level import block when the predicate is implemented.

def test_is_publishable_book_skips_when_both_none() -> None:
    from data_svc.market_selection import is_publishable_book

    assert is_publishable_book(None, None) is False


def test_is_publishable_book_skips_when_bid_none() -> None:
    """A missing side is missing data, not a tradeable zero -> not publishable."""
    from data_svc.market_selection import is_publishable_book

    assert is_publishable_book(None, Decimal("5")) is False


def test_is_publishable_book_skips_when_ask_none() -> None:
    from data_svc.market_selection import is_publishable_book

    assert is_publishable_book(Decimal("5"), None) is False


def test_is_publishable_book_skips_when_both_zero() -> None:
    """Both sides zero -> genuinely dead book -> not publishable."""
    from data_svc.market_selection import is_publishable_book

    assert is_publishable_book(Decimal("0"), Decimal("0")) is False


def test_is_publishable_book_passes_when_only_ask() -> None:
    """Heavy favorite: no yes-bid, a real yes-ask. The market we set out to
    keep (OR semantics)."""
    from data_svc.market_selection import is_publishable_book

    assert is_publishable_book(Decimal("0"), Decimal("0.6")) is True


def test_is_publishable_book_passes_when_only_bid() -> None:
    """Mirror case: a real yes-bid, no yes-ask -> one real quote -> publishable."""
    from data_svc.market_selection import is_publishable_book

    assert is_publishable_book(Decimal("0.6"), Decimal("0")) is True


def test_is_publishable_book_passes_when_both_present() -> None:
    from data_svc.market_selection import is_publishable_book

    assert is_publishable_book(Decimal("48"), Decimal("49")) is True


# --- one-sided heavy-favorite books (OR semantics) ---------------------

def test_evaluate_passes_one_sided_favorite() -> None:
    """yes_bid=0 with a real yes_ask is a publishable one-sided book; NO is
    mirror algebra. Today this wrongly skips as NO_BOOK. volume_fp=5000 keeps
    the test on the BOOK path (>= default floor 1000)."""
    m = _market(
        ticker="KXMVESPORTSMULTIGAMEEXTENDED-S2026ABC",
        yes_bid_dollars="0.0000",
        yes_ask_dollars="0.0200",
        no_bid_dollars="0.9800",  # mirror: 1 - yes_ask
        no_ask_dollars="1.0000",  # mirror: 1 - yes_bid
        volume_fp="5000.00",
    )
    result = evaluate(m, _config())
    assert result.passed is True
    assert result.reason is None
    assert result.tier == Tier.DEFAULT


def test_evaluate_one_sided_favorite_bypasses_spread() -> None:
    """A one-sided book has no round-trip, so SPREAD_TOO_WIDE must not apply.

    Uses a=6c on the DEFAULT tier (cap 5c): if spread were (wrongly) measured
    as a-b it would be 6c > 5c and fail. Asserting passed=True is what proves
    the bypass has teeth. (Deviates from the matrix's a=2c, which is < cap and
    so would never exercise the bypass; flagged for review.)"""
    m = _market(
        ticker="KXMVESPORTSMULTIGAMEEXTENDED-S2026DEF",
        yes_bid_dollars="0.0000",
        yes_ask_dollars="0.0600",  # a-b would be 6c > default 5c if measured
        no_bid_dollars="0.9400",
        no_ask_dollars="1.0000",
        volume_fp="5000.00",
    )
    result = evaluate(m, _config())
    assert result.passed is True
    assert result.reason is None


def test_evaluate_still_skips_dead_book() -> None:
    """Both sides zero -> genuinely no book -> NO_BOOK (preserved)."""
    m = _market(
        ticker="KXMVE-DEAD",
        yes_bid_dollars="0.0000",
        yes_ask_dollars="0.0000",
        no_bid_dollars="1.0000",
        no_ask_dollars="1.0000",
        volume_fp="5000.00",
    )
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.NO_BOOK


def test_evaluate_still_skips_missing_side() -> None:
    """A missing YES quote (None, not 0) is missing data -> NO_BOOK (preserved)."""
    m = _market(ticker="KXMVE-MISSING", volume_fp="5000.00")
    del m["yes_bid_dollars"]
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.NO_BOOK


def test_evaluate_two_sided_wide_still_spread_skips() -> None:
    """A real two-sided book with a wide spread still skips SPREAD_TOO_WIDE:
    the OR/bypass change must not weaken spread enforcement for round-trips."""
    m = _market(
        ticker="KXFED-WIDE",
        yes_bid_dollars="0.4000",
        yes_ask_dollars="0.5500",  # 15c spread > tight 2c
        no_bid_dollars="0.4500",
        no_ask_dollars="0.6000",
        volume_fp="5000.00",
    )
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.SPREAD_TOO_WIDE


def test_evaluate_one_sided_favorite_below_volume_still_skips() -> None:
    """The book fix must NOT bypass the volume gate: a publishable one-sided
    book with sub-floor volume still skips VOLUME_TOO_LOW (today: NO_BOOK)."""
    m = _market(
        ticker="KXMVESPORTSMULTIGAMEEXTENDED-S2026LOWVOL",
        yes_bid_dollars="0.0000",
        yes_ask_dollars="0.0200",
        no_bid_dollars="0.9800",
        no_ask_dollars="1.0000",
        volume_fp="10.00",  # < default 1000
    )
    result = evaluate(m, _config())
    assert result.passed is False
    assert result.reason == SkipReason.VOLUME_TOO_LOW
