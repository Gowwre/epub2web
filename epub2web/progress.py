"""Cooperative progress reporting for long-running conversion stages.

Core modules report phase-local work through a simple callable. The CLI wraps
that callable in :class:`ProgressPrinter` when ``--progress`` is used, giving
the desktop GUI a machine-readable stream without coupling the converter to a
GUI toolkit.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import TextIO

PROGRESS_PREFIX = "@@epub2web:progress "

# phase -> (start, end) as a fraction of the overall build. The image stage is
# deliberately given the largest share because decoding/re-encoding dominates
# real-world books.
PHASE_BOUNDS: dict[str, tuple[float, float]] = {
    "read": (0.00, 0.03),
    "extract-images": (0.03, 0.62),
    "extract-pages": (0.62, 0.72),
    "extract-write": (0.72, 0.75),
    "render-pages": (0.75, 0.88),
    "render-assets": (0.88, 0.91),
    "verify": (0.91, 0.95),
    "links": (0.95, 0.985),
    "publish": (0.985, 1.00),
    "preview": (1.00, 1.00),
}

ProgressCallback = Callable[[str, str, int, int], None]


class ProgressPrinter:
    """Turn phase-local progress into monotonic overall progress lines."""

    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        prefix: str = PROGRESS_PREFIX,
    ) -> None:
        self.stream = stream or sys.stdout
        self.prefix = prefix
        self._last_percent = 0.0

    def __call__(self, phase: str, label: str, current: int, total: int) -> None:
        start, end = PHASE_BOUNDS.get(phase, (0.0, 1.0))
        fraction = 1.0 if total <= 0 else max(0.0, min(1.0, current / total))
        percent = start + (end - start) * fraction
        percent = max(self._last_percent, min(1.0, percent))
        self._last_percent = percent
        payload = {
            "phase": phase,
            "label": label,
            "current": current,
            "total": total,
            "percent": round(percent, 4),
        }
        print(
            self.prefix + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            file=self.stream,
            flush=True,
        )


def report(
    callback: ProgressCallback | None,
    phase: str,
    label: str,
    current: int,
    total: int,
) -> None:
    """Call *callback* when progress reporting is enabled."""
    if callback is not None:
        callback(phase, label, current, total)
