"""Failing-first tests for new data-svc selection settings.

Config is policy (Lesson 9): tiers and thresholds live in Settings, not
code. Env-parseable means CSV / scalar strings, not raw Python dicts.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from data_svc.settings import Settings


def test_settings_parses_named_series_prefixes_from_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_SVC_NAMED_SERIES_PREFIXES", "KXFED,KXPRES,KXECON")
    settings = Settings()
    assert "KXFED" in settings.named_series_prefixes
    assert "KXECON" in settings.named_series_prefixes
    assert len(settings.named_series_prefixes) == 3


def test_selection_config_built_from_settings_defaults() -> None:
    config = Settings().selection_config()
    assert config.tight_max_spread_cents == Decimal("2")
    assert config.default_min_volume_24h == 1000
    assert "KXFED" in config.named_series_prefixes
