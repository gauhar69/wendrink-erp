"""
WENDRINK ERP - In-Memory Cache with TTL

Simple in-memory cache for dashboard metrics.
Invalidated on any write operation (sale, supply, finance).

Why cache?
- Dashboard P&L requires 3 aggregate queries (Revenue, COGS, OPEX)
- Inventory status requires N queries (one per ingredient)
- These values change ONLY when data is written
- Cache for 5 minutes = dashboard loads instantly

LAW COMPLIANCE:
- Law 1: Cache does NOT store balances — only pre-computed view results
- Cache is invalidated on every write, so values are always fresh
"""

from datetime import datetime, timedelta
from typing import Any
import logging

logger = logging.getLogger(__name__)

# Global cache storage
_cache: dict[str, Any] = {}
_cache_expiry: dict[str, datetime] = {}

# Default TTL: 5 minutes
DEFAULT_TTL = 300


def get_cached(key: str) -> Any | None:
    """
    Get cached value if it exists and hasn't expired.
    
    Returns None if cache miss or expired.
    """
    if key not in _cache:
        return None
    
    if datetime.now() > _cache_expiry[key]:
        # Expired — remove
        del _cache[key]
        del _cache_expiry[key]
        return None
    
    logger.debug(f"Cache HIT: {key}")
    return _cache[key]


def set_cached(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """
    Store value in cache with TTL (seconds).
    """
    _cache[key] = value
    _cache_expiry[key] = datetime.now() + timedelta(seconds=ttl)
    logger.debug(f"Cache SET: {key} (TTL={ttl}s)")


def invalidate_cache(prefix: str = "") -> None:
    """
    Invalidate cache entries matching prefix.
    
    If prefix is empty, invalidate ALL cache entries.
    Called after any write operation (sale, supply, finance, correction).
    """
    if not prefix:
        count = len(_cache)
        _cache.clear()
        _cache_expiry.clear()
        if count > 0:
            logger.info(f"Cache INVALIDATED: all {count} entries")
        return
    
    keys_to_delete = [k for k in _cache if k.startswith(prefix)]
    for k in keys_to_delete:
        del _cache[k]
        del _cache_expiry[k]
    
    if keys_to_delete:
        logger.info(f"Cache INVALIDATED: {len(keys_to_delete)} entries with prefix '{prefix}'")


def cache_stats() -> dict:
    """
    Get cache statistics for monitoring.
    """
    now = datetime.now()
    active = sum(1 for k in _cache_expiry if _cache_expiry[k] > now)
    expired = len(_cache) - active
    
    return {
        "total_entries": len(_cache),
        "active": active,
        "expired": expired,
    }
