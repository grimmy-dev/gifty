"""Central handling for retryable rate-limit and network errors."""

import logging
import random
import time
from typing import Callable, TypeVar

log = logging.getLogger("gifty.errors")

T = TypeVar("T")

RETRYABLE_CODES = {429, 500, 502, 503, 504}
RETRYABLE_HINTS = ("connection", "timeout", "unavailable", "overloaded", "ratelimit")


def is_retryable(exc: Exception) -> bool:
    """Return True for transient provider/network errors worth retrying."""
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code in RETRYABLE_CODES:
        return True
    name = type(exc).__name__.lower()
    return any(hint in name for hint in RETRYABLE_HINTS)


def retry_call(fn: Callable[..., T], *args, attempts: int = 3, base: float = 5.0, **kwargs) -> T:
    """Call fn with jittered exponential backoff on retryable errors.

    Args:
        attempts: Max attempts before giving up.
        base: Backoff base seconds; delay = base * 2**i + jitter.
    """
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not is_retryable(exc) or i == attempts - 1:
                raise
            delay = base * (2**i) + random.uniform(0, base)
            log.warning("retryable error (%s); attempt %d/%d, sleeping %.1fs", exc, i + 1, attempts, delay)
            time.sleep(delay)
    raise RuntimeError("unreachable")
