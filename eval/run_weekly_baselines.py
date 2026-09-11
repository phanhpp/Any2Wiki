"""Weekly CI pipeline — fetch live traces and refresh baselines.

Intentionally limited to two steps:
    1. Fetch last N days of traces from LangSmith
    2. compute_baselines_async  — update rolling per-run-name medians in
       memories/baselines.json so detect_anomalies_async has a fresh 3x threshold

Steps 3-4 (detect anomalies -> push to LangSmith datasets) are HITL-only.
They run via the trace-analysis skill, where a human reviews the anomaly report
before any dataset write happens. Pushing datasets automatically risks committing
infrastructure noise (chain-level OOM / network timeouts) as regression examples.

There is no weekly replay job. A hard error becomes durable coverage by being
promoted into eval/pr_gate_cases.json, which runs on every PR — strictly more often
than a weekly replay would. See eval/README.md.

Baseline drift is reported, not gated. detect_anomalies_async only fires when a run
exceeds 3x the median, so a slow, steady regression raises the median along with it
and the spike check goes quiet — the regression gets absorbed into "normal". To catch
that, compute_baselines_async compares each refreshed median against the one it
replaces and returns anything that moved more than DRIFT_THRESHOLD. This script prints
those lines and, in CI, appends them to $GITHUB_STEP_SUMMARY. It never fails the job:
a moved median is a question for a human, not a broken build.

Run:
    uv run --env-file .env python eval/run_weekly_baselines.py
    uv run --env-file .env python eval/run_weekly_baselines.py --days 14 --limit 200
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add repo root to sys.path so `import src` works when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.observability_eval_tools.fetch_traces import run_trace_report_async
from src.tools.observability_eval_tools.anomaly_detection import (
    DRIFT_THRESHOLD,
    compute_baselines_async,
)

# Use .coroutine to call the underlying async function directly —
# bypasses LangChain tool validation overhead, appropriate for a script.
_fetch     = run_trace_report_async.coroutine
_baselines = compute_baselines_async.coroutine


async def run(project: str, days: int, limit: int) -> int:
    """Run the baseline-refresh pipeline. Returns exit code (0 = success, 1 = fatal error)."""

    # -- 1. Fetch traces -------------------------------------------------------
    print(f"[weekly] Fetching traces: project={project!r} days={days} limit={limit}")
    report = await _fetch(project=project, days=days, limit=limit)

    print(f"[weekly] Fetched {report.trace_count} traces (offloaded={report.is_offloaded})")

    if not report.trace_count:
        print("[weekly] No traces found — skipping baseline update.")
        return 0

    # -- 2. Update baselines ---------------------------------------------------
    # Overwrites memories/baselines.json with fresh per-run-name medians.
    # detect_anomalies_async uses these as the 3x spike threshold — running
    # weekly keeps baselines from drifting as traffic patterns change.
    print("[weekly] Updating baselines...")
    baseline_result = await _baselines(report=report)
    n_name = len(baseline_result.get("by_name", {}))
    n_flow = len(baseline_result.get("by_flow", {}))
    print(f"[weekly] Baselines updated: {n_name} run-name entries, {n_flow} flow entries")

    # -- 3. Report drift -------------------------------------------------------
    # Never changes the exit code. See the module docstring: a median that moved is
    # a question for a human, not a failed build.
    _report_drift(baseline_result.get("drift", []))

    return 0


def _format_drift(drift: list[dict]) -> list[str]:
    """One line per moved median, e.g. ``wiki-ingestion  median_steps  2 -> 9 (+350%)``."""
    lines = []
    for d in sorted(drift, key=lambda d: abs(d["change"]), reverse=True):
        before, after, pct = d["before"], d["after"], d["change"] * 100
        lines.append(f"{d['key']}  {d['metric']}  {before:g} -> {after:g} ({pct:+.0f}%)")
    return lines


def _report_drift(drift: list[dict]) -> None:
    """Print moved medians, and append them to the CI job summary when running in CI."""
    if not drift:
        print("[weekly] No baseline drift over threshold.")
        return

    lines = _format_drift(drift)
    print(f"[weekly] {len(lines)} baseline(s) moved >{DRIFT_THRESHOLD:.0%} since last refresh:")
    for line in lines:
        print(f"[weekly]   {line}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    body = "\n".join(f"- `{line}`" for line in lines)
    with open(summary, "a", encoding="utf-8") as f:
        f.write(
            f"\n### Baseline drift (>{DRIFT_THRESHOLD:.0%})\n\n"
            f"{body}\n\n"
            "A median moving this much means the spike check is now measuring against a "
            "different normal. Worth a look; not a build failure.\n"
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", default="paper2wiki", help="LangSmith project name")
    # 60 days / 500 traces: a median is only as good as its sample count, and the
    # previous 30/100 left per-flow buckets with 3 samples — small enough that the
    # median moved on noise and normal runs tripped the 3x spike check.
    p.add_argument("--days",    type=int, default=60,  help="Lookback window in days")
    p.add_argument("--limit",   type=int, default=500, help="Max traces to fetch")
    return p.parse_args()


if __name__ == "__main__":
    from src.env import load_env

    load_env()
    args = parse_args()
    sys.exit(asyncio.run(run(project=args.project, days=args.days, limit=args.limit)))
