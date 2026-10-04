"""Defensive statistics calculation for latency measurements."""

import statistics
from typing import Optional, Sequence, Tuple


def calculate_latency_stats(
    samples: Sequence[float],
    failed_count: int = 0
) -> Tuple[Optional[float], Optional[float], Optional[float], int]:
    """
    Calculate median, min, max, and failed count defensively.

    Args:
        samples: A sequence of successful numeric latency values in milliseconds.
        failed_count: Total number of failed measurement attempts.

    Returns:
        (median, min, max, failed_count)
    """
    valid_samples = [s for s in samples if isinstance(s, (int, float)) and s >= 0]

    if not valid_samples:
        return None, None, None, failed_count

    med = round(float(statistics.median(valid_samples)), 2)
    min_val = round(float(min(valid_samples)), 2)
    max_val = round(float(max(valid_samples)), 2)

    return med, min_val, max_val, failed_count
