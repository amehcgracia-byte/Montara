"""Regression coverage for isolated EX-06 opt-in adapter (not a production switch)."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
from core import spherical_motion
from experiments.media_optimization.jupiter_cpu_linear_optin import cpu_bilinear_optin


def _sample():
    frame = np.arange(32 * 64 * 3, dtype=np.uint8).reshape(32, 64, 3)
    xx, yy = np.meshgrid(np.arange(48, dtype=np.float32) + 0.37,
                         np.arange(24, dtype=np.float32) + 0.23)
    return frame, xx, yy


def test_interpolation_switch_and_restore():
    frame, xx, yy = _sample()
    reference = spherical_motion.cv2
    expected = cv2.remap(frame, xx, yy, interpolation=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_WRAP)
    with cpu_bilinear_optin() as metrics:
        got = spherical_motion.cv2.remap(frame, xx, yy,
                                         interpolation=cv2.INTER_CUBIC,
                                         borderMode=cv2.BORDER_WRAP)
        assert metrics.cubic_to_linear_calls == 1
        assert metrics.other_remap_calls == 0
    np.testing.assert_array_equal(got, expected)
    assert spherical_motion.cv2 is reference


def test_other_interpolations_unchanged():
    frame, xx, yy = _sample()
    expected = cv2.remap(frame, xx, yy, interpolation=cv2.INTER_NEAREST,
                         borderMode=cv2.BORDER_WRAP)
    with cpu_bilinear_optin() as metrics:
        got = spherical_motion.cv2.remap(frame, xx, yy,
                                         interpolation=cv2.INTER_NEAREST,
                                         borderMode=cv2.BORDER_WRAP)
        assert metrics.cubic_to_linear_calls == 0
        assert metrics.other_remap_calls == 1
    np.testing.assert_array_equal(got, expected)


def test_restores_on_exception():
    original = spherical_motion.cv2
    with pytest.raises(ZeroDivisionError):
        with cpu_bilinear_optin():
            raise ZeroDivisionError("expected")
    assert spherical_motion.cv2 is original


def test_nested_override_rejected_and_restored():
    original = spherical_motion.cv2
    with cpu_bilinear_optin():
        with pytest.raises(RuntimeError, match="Nested or concurrent"):
            with cpu_bilinear_optin():
                pass
    assert spherical_motion.cv2 is original
