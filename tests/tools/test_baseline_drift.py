"""Unit tests for baseline drift detection — the check that keeps a slow regression
from being absorbed into the median it is measured against."""
from __future__ import annotations

import pytest

from src.tools.observability_eval_tools.anomaly_detection import (
    DRIFT_THRESHOLD,
    MINIMUM_SAMPLES,
    _drift,
)

_ENOUGH = MINIMUM_SAMPLES


def _entry(**kw) -> dict:
    """A baseline entry with enough samples to be trusted unless overridden."""
    return {"sample_count": _ENOUGH, **kw}


@pytest.mark.unit
def test_flags_a_median_that_moved_past_the_threshold() -> None:
    """A latency median that doubled is reported with its before/after and ratio."""
    moved = _drift(
        _entry(median_latency=10.0),
        _entry(median_latency=20.0),
        ("median_latency",),
    )
    assert len(moved) == 1
    assert moved[0]["metric"] == "median_latency"
    assert moved[0]["before"] == 10.0
    assert moved[0]["after"] == 20.0
    assert moved[0]["change"] == pytest.approx(1.0)


@pytest.mark.unit
def test_ignores_a_move_under_the_threshold() -> None:
    """Ordinary week-to-week wobble must stay silent, or the report becomes noise."""
    assert _drift(
        _entry(median_latency=10.0),
        _entry(median_latency=10.0 * (1 + DRIFT_THRESHOLD / 2)),
        ("median_latency",),
    ) == []


@pytest.mark.unit
def test_flags_improvements_too() -> None:
    """A median that dropped sharply is equally worth knowing — it may mean a flow
    stopped running, not that it got faster."""
    moved = _drift(_entry(median_steps=8), _entry(median_steps=2), ("median_steps",))
    assert len(moved) == 1
    assert moved[0]["change"] < 0


@pytest.mark.unit
@pytest.mark.parametrize("old_n,new_n", [(MINIMUM_SAMPLES - 1, _ENOUGH), (_ENOUGH, MINIMUM_SAMPLES - 1)])
def test_skipped_when_either_side_is_undersampled(old_n: int, new_n: int) -> None:
    """A median over too few samples swings on noise; comparing it reports nothing real."""
    assert _drift(
        {"sample_count": old_n, "median_latency": 10.0},
        {"sample_count": new_n, "median_latency": 100.0},
        ("median_latency",),
    ) == []


@pytest.mark.unit
def test_no_previous_entry_is_not_drift() -> None:
    """A brand-new baseline has nothing to have moved from."""
    assert _drift(None, _entry(median_latency=10.0), ("median_latency",)) == []


@pytest.mark.unit
@pytest.mark.parametrize("before", [None, 0])
def test_unusable_previous_value_is_skipped(before) -> None:
    """``None`` means the metric was never established and 0 has no ratio."""
    assert _drift(
        _entry(median_tokens=before),
        _entry(median_tokens=5000),
        ("median_tokens",),
    ) == []


@pytest.mark.unit
def test_reports_each_moved_metric_separately() -> None:
    """Latency and tokens are independent signals and must not collapse into one row."""
    moved = _drift(
        _entry(median_latency=1.0, median_tokens=100),
        _entry(median_latency=5.0, median_tokens=900),
        ("median_latency", "median_tokens"),
    )
    assert {m["metric"] for m in moved} == {"median_latency", "median_tokens"}
