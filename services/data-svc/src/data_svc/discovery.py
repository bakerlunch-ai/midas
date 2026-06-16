"""Discovery loop for data-svc — the slow universe scanner.

Paginates ALL open Kalshi markets on a slow cadence, applies the
``market_selection`` filter, and maintains the in-memory selected universe
that the fast tick-poll loop consults. Universe changes slowly; books change
fast — hence two loops with different cadences.

The selected universe is intentionally NOT persisted (Lesson 8: no state
without a reader). On pod restart it rebuilds on the first discovery cycle;
the tick loop no-ops until then.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from data_svc.market_selection import (
    SelectionConfig,
    Tier,
    evaluate,
    summarize_selected_by_series,
)

if TYPE_CHECKING:
    from data_svc.kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveryResult:
    """Outcome of one discovery scan."""

    selected: frozenset[str]
    scanned: int
    by_series: dict[str, int]
    by_tier: dict[Tier, int]


class SelectedUniverse:
    """Shared, atomically-replaceable set of selected tickers.

    Single-threaded asyncio: ``replace`` rebinds an immutable frozenset in
    one statement (no await mid-swap), so a ``snapshot`` taken by the tick
    loop is never torn by a concurrent discovery update.
    """

    def __init__(self) -> None:
        self._tickers: frozenset[str] = frozenset()

    def replace(self, tickers: set[str] | frozenset[str]) -> None:
        self._tickers = frozenset(tickers)

    def snapshot(self) -> frozenset[str]:
        return self._tickers


async def discover_once(
    kalshi: KalshiClient, config: SelectionConfig
) -> DiscoveryResult:
    """Paginate all open markets, evaluate each, return the selected set
    plus per-series and per-tier counts for the enriched log."""
    markets = await kalshi.list_all_markets()
    selected: set[str] = set()
    by_tier: dict[Tier, int] = {}
    for i, market in enumerate(markets):
        result = evaluate(market, config)
        if result.passed:
            selected.add(market.get("ticker") or "")
            by_tier[result.tier] = by_tier.get(result.tier, 0) + 1
        # Yield every 1000 markets: this scan is otherwise await-free and would
        # block the event loop (and /health) for the full universe.
        if (i + 1) % 1000 == 0:
            await asyncio.sleep(0)
    return DiscoveryResult(
        selected=frozenset(selected),
        scanned=len(markets),
        by_series=summarize_selected_by_series(selected, config),
        by_tier=by_tier,
    )


def _format_universe_line(result: DiscoveryResult) -> str:
    """Build the enriched discovery log line:

    ``universe=N selected=M scope=tight+default (KXFED=X ... other=W)``
    """
    scope = "+".join(
        tier.value
        for tier in (Tier.TIGHT, Tier.DEFAULT)
        if result.by_tier.get(tier, 0) > 0
    ) or "none"
    breakdown = " ".join(f"{k}={v}" for k, v in sorted(result.by_series.items()))
    return (
        f"universe={result.scanned} selected={len(result.selected)} "
        f"scope={scope} ({breakdown})"
    )


async def discovery_loop(
    kalshi: KalshiClient,
    universe: SelectedUniverse,
    config: SelectionConfig,
    interval_seconds: int,
    *,
    seeded: bool = False,
) -> None:
    """Maintain the selected universe on a slow cadence.

    By default (``seeded=False``) it scans immediately at the top of the first
    cycle. When ``seeded=True`` the caller has already populated the universe
    (await-first startup), so the loop sleeps one interval before its first
    scan — avoiding a redundant back-to-back scan at boot.

    Per-iteration errors are logged and the loop continues; only
    CancelledError breaks out (propagated so shutdown actually terminates)."""
    logger.info(
        "discovery_loop starting: interval=%ds seeded=%s", interval_seconds, seeded
    )
    first = True
    while True:
        if seeded and first:
            # Universe already seeded by the caller; wait a full interval
            # before the first refresh instead of scanning immediately.
            await asyncio.sleep(interval_seconds)
        first = False
        try:
            result = await discover_once(kalshi, config)
            universe.replace(result.selected)
            logger.info("discovery complete: %s", _format_universe_line(result))
        except asyncio.CancelledError:
            logger.info("discovery_loop cancelled, exiting")
            raise
        except Exception:
            logger.exception("discovery_loop iteration raised; continuing")
        await asyncio.sleep(interval_seconds)
