#!/usr/bin/env python
"""Verify every model ID in MODELS.md still exists at its provider.

Model IDs rot. Providers retire them without warning and the only symptom is a 404 in the
middle of a run — `gemini-2.0-flash` and `deepseek-r1:free` were both in this repo's docs
until they stopped resolving. This asks each provider's catalog endpoint instead of
trusting the document.

    uv run --env-file .env python scripts/check_model_ids.py            # scan MODELS.md
    uv run --env-file .env python scripts/check_model_ids.py openai:gpt-4o qwen/qwen3-32b

Needs ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY for those catalogs; OpenRouter's
is public. A provider whose key is missing is skipped, not failed.

Exit codes: 0 all known IDs resolve · 1 at least one is gone.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _get(url: str, headers: dict) -> dict:
    try:
        req = urllib.request.Request(url, headers=headers)
        return json.load(urllib.request.urlopen(req, timeout=25))
    except Exception as exc:  # unreachable catalog is "unknown", never "gone"
        return {"__err__": f"{type(exc).__name__}: {str(exc)[:70]}"}


def catalogs() -> dict[str, set[str] | None]:
    """Live model IDs per provider. ``None`` means we could not ask (missing key, outage)."""
    out: dict[str, set[str] | None] = {}

    if k := os.environ.get("ANTHROPIC_API_KEY"):
        d = _get("https://api.anthropic.com/v1/models?limit=100",
                 {"x-api-key": k, "anthropic-version": "2023-06-01"})
        out["anthropic"] = None if "__err__" in d else {m["id"] for m in d["data"]}
    else:
        out["anthropic"] = None

    if k := os.environ.get("OPENAI_API_KEY"):
        d = _get("https://api.openai.com/v1/models", {"Authorization": f"Bearer {k}"})
        out["openai"] = None if "__err__" in d else {m["id"] for m in d["data"]}
    else:
        out["openai"] = None

    if k := os.environ.get("GOOGLE_API_KEY"):
        d = _get(f"https://generativelanguage.googleapis.com/v1beta/models?key={k}", {})
        out["google_genai"] = None if "__err__" in d else {
            m["name"].replace("models/", "") for m in d.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        }
    else:
        out["google_genai"] = None

    d = _get("https://openrouter.ai/api/v1/models", {})  # public, no key
    out["openrouter"] = None if "__err__" in d else {m["id"] for m in d["data"]}
    return out


def classify(model: str) -> tuple[str | None, str]:
    """(provider, bare id) for a model string, or (None, …) when we cannot tell."""
    if ":" in model and not model.endswith(":free") and "/" not in model.split(":")[0]:
        prefix, rest = model.split(":", 1)
        if prefix in {"anthropic", "openai", "google_genai", "openrouter"}:
            return ("openrouter" if prefix == "openrouter" else prefix), rest
    if model.startswith("claude-"):
        return "anthropic", model
    if model.startswith(("gpt-", "o1", "o3")):
        return "openai", model
    if model.startswith("gemini-"):
        return "google_genai", model
    if "/" in model:                    # provider/model → an OpenRouter slug
        return "openrouter", model
    return None, model


def scan_models_md() -> list[str]:
    """Model IDs appearing in MODELS.md fenced blocks — the list this guards."""
    text = (REPO / "MODELS.md").read_text()
    # Hostnames, paths and wildcards look like model slugs to a regex. Skip anything with a
    # TLD-ish dot before the first slash, a URL scheme, or a glob.
    SKIP = re.compile(r"^(https?|sk-|ANY2WIKI|LITELLM)|[.](com|ai|io|org|net)([/:]|$)|[*]|/v\d")
    found: list[str] = []
    for line in text.splitlines():
        line = line.split("#")[0].strip().rstrip(",")
        for tok in re.findall(r"[A-Za-z0-9_.\-]+(?:[:/][A-Za-z0-9_.\-]+)+", line):
            # a trailing "-" means the regex stopped at a glob: `llama-4-*`
            if SKIP.search(tok) or tok.endswith((".md", ".py", ".yaml", ".json", "-")):
                continue
            found.append(tok)
    return sorted(set(found))


def main() -> int:
    wanted = sys.argv[1:] or scan_models_md()
    cats = catalogs()
    for p, v in cats.items():
        if v is None:
            print(f"  (skipping {p} — no key, or the catalog did not answer)")

    gone, ok, unknown = [], 0, 0
    for m in wanted:
        provider, bare = classify(m)
        known = cats.get(provider) if provider else None
        if known is None:
            unknown += 1
            continue
        if bare in known:
            ok += 1
        else:
            gone.append((m, provider))

    for m, p in gone:
        print(f"  GONE  {m}   (not in {p}'s catalog)")
    print(f"\n  {ok} ok · {len(gone)} gone · {unknown} unchecked")
    return 1 if gone else 0


if __name__ == "__main__":
    raise SystemExit(main())
