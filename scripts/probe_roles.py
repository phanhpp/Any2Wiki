"""Can this provider actually run all six of our model tasks?

**This makes six real API calls** — one per task — and costs a fraction of a cent. It is
not a dry run; `config show` and `scripts/check_provider_configs.sh` are the free checks
that only verify *resolution*. This one verifies the provider answers.

Six calls rather than one, because the tasks resolve to different models and a provider can
support one call shape and not another:

    supervisor / subagent / title / web_summarize  → plain completion
    summarize / judge                              → with_structured_output

**What this does not prove.** It sends one trivial message per task with **no tools bound**,
so it never exercises tool calling, the agent loop, HITL, streaming, middleware or a wiki
write. A green run means *this provider answers for every task's model* — the model layer.
It does not mean the app works on that provider. For that, see the end-to-end checks in
`docs/models/provider_testing.md` (tier 2).

Usage:
    uv run --env-file .env python <this> openai:gpt-4o   # force every task to one model
    uv run --env-file .env python <this>                 # whatever config.yaml resolves to

Passing a model **forces all six tasks onto it**. Without that, `config.yaml`'s
`auxiliary.<task>` pins still apply, so you would be testing a mix — which is a fine way to
check your real setup, but not a way to test one provider.

Reading the output:

    [  ok  ]   the provider returned a usable answer
    [ BUILD]   the client could not even be constructed — bad config, missing key
    [ CALL ]   the client was built but the request failed — wrong model name, no quota,
               or the provider does not support what the task needs

Exit codes: 0 all six passed · 1 at least one failed · 2 the model override did not take
(nothing was tested — see the guard near the bottom).
"""

import sys

from pydantic import BaseModel, Field

from src.env import load_env

load_env()

MODEL = sys.argv[1] if len(sys.argv) > 1 else None
if MODEL:
    import os

    # Point every task at the requested model, not just the base one.
    #
    # ANY2WIKI_MODEL alone is *level 3*, which loses to a task pinned in config.yaml at
    # level 2 — and config.yaml pins five tasks to haiku. Setting it by itself would move
    # only the supervisor and keep quietly testing Anthropic for the other five. The
    # per-task vars below are level 1, the only thing that beats a config pin.
    os.environ["ANY2WIKI_MODEL"] = MODEL
    for role in ("SUPERVISOR", "SUBAGENT", "TITLE", "SUMMARIZE", "JUDGE", "WEB_SUMMARIZE"):
        os.environ[f"ANY2WIKI_MODEL_{role}"] = MODEL

# Imported after the env vars are set — get_model_spec reads them at call time, but keeping
# the order explicit makes the dependency obvious.
from src.agents.llms import set_up_llms          # noqa: E402
from src.llm_roles import VALID_ROLES, get_model_spec  # noqa: E402


class _Verdict(BaseModel):
    """A stand-in for what `judge` and `summarize` really ask a model to produce.

    The point is the **typed** `score`: a provider can accept `with_structured_output`,
    return HTTP 200, and still hand back something that does not match the schema. Asking
    for a real `int` is what catches that — checking only that a response arrived would not.
    """

    score: int = Field(description="0 or 1")
    reason: str


def probe(role: str) -> tuple[str, str]:
    """Build this task's model and make one real call with it.

    Two failures are worth telling apart, so they are separate statuses:

    * ``BUILD FAIL`` — ``set_up_llms`` raised. Nothing was sent; the config or key is wrong.
    * ``CALL FAIL``  — the client was built and the *provider* rejected the request.

    Returns ``(status, one-line detail)``; the caller prints and tallies them.
    """
    spec = get_model_spec(role)
    label = f"{spec.model}" + (f" via {spec.base_url}" if spec.base_url else "")
    try:
        llm = set_up_llms(spec)
    except Exception as exc:
        return "BUILD FAIL", f"{label} — {type(exc).__name__}: {str(exc)[:70]}"

    # `judge` and `summarize` are the two tasks that need a typed object back, so they get
    # the harder call. The other four only need text.
    structured = role in {"summarize", "judge"}
    try:
        if structured:
            out = llm.with_structured_output(_Verdict).invoke(
                [{"role": "user", "content": "Score this 1 and say 'ok'."}]
            )
            assert isinstance(out.score, int), "score is not an int"
            detail = f"structured → score={out.score}"
        else:
            out = llm.invoke([{"role": "user", "content": "Reply with exactly: ok"}])
            text = out.content if isinstance(out.content, str) else str(out.content)
            detail = f"text → {text.strip()[:30]!r}"
        return "OK", f"{label} — {detail}"
    except Exception as exc:
        return "CALL FAIL", f"{label} — {type(exc).__name__}: {str(exc)[:90]}"


print(f"\nProbing roles with: {MODEL or '(config.yaml defaults)'}\n")

# Refuse to run if the override did not reach every task.
#
# A false pass is worse than a failure here. This script once set `PAPER2WIKI_MODEL_*`
# after the rename to `ANY2WIKI_*`, so nothing read it: all six tasks quietly resolved to
# Anthropic and it printed "All roles OK" for a provider it had never contacted. Exit 2
# says "nothing was tested", which is different from "something failed" (exit 1).
if MODEL:
    wrong = [r for r in sorted(VALID_ROLES) if get_model_spec(r).model != MODEL]
    if wrong:
        print(f"  override did not reach: {', '.join(wrong)}")
        print(f"  every role must resolve to {MODEL!r} — the probe would test the wrong "
              "model and still pass")
        sys.exit(2)
worst = 0
for role in sorted(VALID_ROLES):
    status, detail = probe(role)
    mark = {"OK": "  ok  ", "BUILD FAIL": " BUILD", "CALL FAIL": " CALL "}[status]
    tag = "  [structured]" if role in {"summarize", "judge"} else ""
    print(f"[{mark}] {role:14} {detail}{tag}")
    worst = max(worst, 0 if status == "OK" else 1)

print("\nAll roles OK." if not worst else "\nSome roles failed — see above.")
sys.exit(worst)
