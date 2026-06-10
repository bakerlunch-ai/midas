"""Market selection rules for data-svc — pure, no I/O (Lesson 5: one place).

``evaluate()`` is the single entry point, deliberately called from two places:
  - ``discovery.discover_once`` (slow loop) to build the selected universe.
  - ``tick_poller._poll_once`` (fast loop) to re-check a selected market's
    FRESH book at publish time. The re-check is what makes the poll-log
    ``(no_book/spread/volume)`` counts meaningful: they show how stable the
    selected universe is between discovery cycles.

Tiering (config-driven, Lesson 9): named macro series get a TIGHT tier
(lower volume floor, tighter spread cap); everything else — including
sports — gets a permissive DEFAULT tier. Open scope: there is no ticker
allowlist. Liquidity, not category, decides.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from data_svc.settings import Settings


class SkipReason(StrEnum):
    """Enumerated, countable reasons a market is not published."""

    NO_BOOK = "no_book"
    SPREAD_TOO_WIDE = "spread"
    VOLUME_TOO_LOW = "volume"


class Tier(StrEnum):
    """Liquidity tier a market is evaluated under."""

    TIGHT = "tight"
    DEFAULT = "default"


@dataclass(frozen=True)
class SelectionConfig:
    """Resolved selection thresholds. Built from Settings; passed to
    ``evaluate`` so the function stays pure (no env reads inside)."""

    named_series_prefixes: frozenset[str]
    tight_max_spread_cents: Decimal
    tight_min_volume_24h: int
    default_max_spread_cents: Decimal
    default_min_volume_24h: int


@dataclass(frozen=True)
class SelectionResult:
    """Outcome of evaluating one market. ``tier`` is recorded even on a
    skip so skip logs can attribute to a tier."""

    passed: bool
    reason: SkipReason | None
    tier: Tier


def dollars_to_cents(raw: Any) -> Decimal | None:
    """Parse a Kalshi dollar string to cents Decimal, or None on bad input."""
    if raw is None:
        return None
    try:
        return Decimal(str(raw)) * 100
    except (InvalidOperation, TypeError, ValueError):
        return None


def fp_to_int(raw: Any) -> int:
    """Parse a Kalshi ``*_fp`` string to int, or 0 on bad input."""
    if raw is None:
        return 0
    try:
        return int(Decimal(str(raw)))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def series_of(ticker: str) -> str:
    """Series prefix = substring before the first '-' (exact, not startswith).

    Splitting on the first dash means ``KXFEDX-...`` resolves to ``KXFEDX``
    and will not false-match the ``KXFED`` named series.
    """
    return ticker.split("-", 1)[0]


def _tier_of(ticker: str, config: SelectionConfig) -> Tier:
    return (
        Tier.TIGHT
        if series_of(ticker) in config.named_series_prefixes
        else Tier.DEFAULT
    )


def evaluate(market: dict[str, Any], config: SelectionConfig) -> SelectionResult:
    """The one selection entry point.

    Resolves tier from the series, then checks in precedence order
    NO_BOOK -> SPREAD_TOO_WIDE -> VOLUME_TOO_LOW (first failure wins). The
    tier is recorded on the result even when the market is skipped.
    """
    ticker = market.get("ticker") or ""
    tier = _tier_of(ticker, config)

    if tier is Tier.TIGHT:
        max_spread = config.tight_max_spread_cents
        min_volume = config.tight_min_volume_24h
    else:
        max_spread = config.default_max_spread_cents
        min_volume = config.default_min_volume_24h

    yes_bid = dollars_to_cents(market.get("yes_bid_dollars"))
    yes_ask = dollars_to_cents(market.get("yes_ask_dollars"))
    no_bid = dollars_to_cents(market.get("no_bid_dollars"))
    no_ask = dollars_to_cents(market.get("no_ask_dollars"))

    # NO_BOOK: any side missing or zero. Emitting a 0 quote is the silent
    # data-quality failure Lesson 8 warns about — skip instead.
    for px in (yes_bid, yes_ask, no_bid, no_ask):
        if px is None or px == 0:
            return SelectionResult(passed=False, reason=SkipReason.NO_BOOK, tier=tier)

    # SPREAD_TOO_WIDE: yes-side spread in cents (no/yes spreads mirror on a
    # binary market; the yes side is the convention).
    assert yes_ask is not None and yes_bid is not None  # narrowed by the loop
    spread = yes_ask - yes_bid
    if spread > max_spread:
        return SelectionResult(
            passed=False, reason=SkipReason.SPREAD_TOO_WIDE, tier=tier
        )

    # VOLUME_TOO_LOW
    volume = fp_to_int(market.get("volume_fp"))
    if volume < min_volume:
        return SelectionResult(
            passed=False, reason=SkipReason.VOLUME_TOO_LOW, tier=tier
        )

    return SelectionResult(passed=True, reason=None, tier=tier)


def summarize_skips(results: Iterable[SelectionResult]) -> dict[SkipReason, int]:
    """Count skip reasons across results (passed results contribute nothing)."""
    counts: dict[SkipReason, int] = {}
    for r in results:
        if not r.passed and r.reason is not None:
            counts[r.reason] = counts.get(r.reason, 0) + 1
    return counts


def summarize_selected_by_series(
    tickers: Iterable[str], config: SelectionConfig
) -> dict[str, int]:
    """Group selected tickers by series; non-named series fold into 'other'."""
    counts: dict[str, int] = {}
    for ticker in tickers:
        series = series_of(ticker)
        key = series if series in config.named_series_prefixes else "other"
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_selection_config(settings: Settings) -> SelectionConfig:
    """Turn runtime Settings into the validated, frozen SelectionConfig that
    the pure evaluate() consumes. Lives here, not on Settings, so all
    selection logic has one home (Lesson 5) and Settings stays plain config."""
    return SelectionConfig(
        named_series_prefixes=frozenset(settings.named_series_prefixes),
        tight_max_spread_cents=settings.tight_max_spread_cents,
        tight_min_volume_24h=settings.tight_min_volume_24h,
        default_max_spread_cents=settings.default_max_spread_cents,
        default_min_volume_24h=settings.default_min_volume_24h,
    )
