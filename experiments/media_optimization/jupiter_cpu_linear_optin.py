#!/usr/bin/env python3
"""JUPITER EX-06: opt-in CPU bilinear remap for ZuckerVideos, without engine edits.

A narrow runtime adapter: patch only the spherical_motion module's cv2 reference
during one synchronous reprojection. No global OpenCV monkeypatch or default change.
Not thread-safe if other jobs concurrently execute spherical_motion in same Python
process; use only in isolated benchmark worker. Metal path remains untouched.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass
class RemapMetrics:
    cubic_to_linear_calls: int = 0
    other_remap_calls: int = 0


class _OpenCvProxy:
    def __init__(self, actual: Any, metrics: RemapMetrics):
        self._actual = actual
        self._metrics = metrics

    def __getattr__(self, name: str) -> Any:
        return getattr(self._actual, name)

    def remap(self, src: Any, map1: Any, map2: Any, *args: Any, **kwargs: Any) -> Any:
        interpolation = kwargs.get("interpolation", args[0] if args else None)
        if interpolation == self._actual.INTER_CUBIC:
            self._metrics.cubic_to_linear_calls += 1
            if "interpolation" in kwargs:
                kwargs = {**kwargs, "interpolation": self._actual.INTER_LINEAR}
            else:
                args = (self._actual.INTER_LINEAR, *args[1:])
        else:
            self._metrics.other_remap_calls += 1
        return self._actual.remap(src, map1, map2, *args, **kwargs)


@contextmanager
def cpu_bilinear_optin():
    """Yield counters with an opt-in only for core.spherical_motion cv2.remap.

    Must be scoped to one single-threaded isolated worker and restored even on
    error. The output is expected to differ from bicubic in pixel values.
    """
    from core import spherical_motion

    original = spherical_motion.cv2
    if isinstance(original, _OpenCvProxy):
        raise RuntimeError("Nested or concurrent EX-06 remap override is forbidden")
    metrics = RemapMetrics()
    spherical_motion.cv2 = _OpenCvProxy(original, metrics)
    try:
        yield metrics
    finally:
        spherical_motion.cv2 = original


def self_test() -> None:
    """Tiny deterministic smoke test; no media files or export required."""
    import cv2
    import numpy as np
    from core import spherical_motion

    frame = np.arange(32 * 64 * 3, dtype=np.uint8).reshape((32, 64, 3))
    x, y = np.meshgrid(np.arange(48, dtype=np.float32) + 0.37,
                       np.arange(24, dtype=np.float32) + 0.23)
    original_cv2 = spherical_motion.cv2
    baseline = original_cv2.remap(frame, x, y, interpolation=cv2.INTER_CUBIC,
                                borderMode=cv2.BORDER_WRAP)
    with cpu_bilinear_optin() as metrics:
        changed = spherical_motion.cv2.remap(
            frame, x, y, interpolation=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_WRAP)
        assert metrics.cubic_to_linear_calls == 1
        assert metrics.other_remap_calls == 0
    expected = cv2.remap(frame, x, y, interpolation=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_WRAP)
    assert np.array_equal(changed, expected), "Opt-in did not select bilinear"
    assert not np.array_equal(baseline, changed), "Fixture fails to distinguish interpolation"
    assert spherical_motion.cv2 is original_cv2, "Original OpenCV reference not restored"

    try:
        with cpu_bilinear_optin():
            raise RuntimeError("intentional test exception")
    except RuntimeError:
        pass
    assert spherical_motion.cv2 is original_cv2, "Override leaked after exception"
    print("EX06_OPTIN_SELFTEST_OK")


if __name__ == "__main__":
    self_test()
