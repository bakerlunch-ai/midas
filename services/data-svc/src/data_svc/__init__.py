"""Midas data ingestion service.

Reads market quotes from Kalshi and emits MarketTickEvent on NATS.
Read-only against Kalshi — no trading endpoints.
"""

__version__ = "0.0.1"
