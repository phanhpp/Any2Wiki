# Choosing and configuring models

Everything about which LLM runs, where the request goes, and how to check before you spend
anything.

**The one command to know:**

```bash
any2wiki config show
```

It prints every task's model, provider and endpoint — resolved exactly the way a real run
resolves them, with no API call. Use it after every change in this document.

---

## The six tasks

**You do not have to set any of these.** One model runs all six. They exist so you *can*
point a task somewhere cheaper or different.


| Task            | What it does                                      | How often it runs       |
| --------------- | ------------------------------------------------- | ----------------------- |
| `supervisor`    | the main agent — plans, calls tools, writes pages | constantly              |
| `subagent`      | the Marp slide subagent                           | only when making slides |
| `title`         | names a session from its first message            | once per session        |
| `summarize`     | condenses traces — **needs structured output**    | trace analysis only     |
| `judge`         | scores eval runs — **needs structured output**    | evals only              |
| `web_summarize` | condenses a scraped web page                      | per web fetch           |




### Setting them

**One model for everything** — this is all most people need:

```yaml
# config.yaml
model:
  default: claude-sonnet-4-6
```

**A different model for one task** — add an `auxiliary` block. Only name the tasks you
want to change; anything you leave out follows `model.default`:

```yaml
model:
  default: claude-sonnet-4-6      # supervisor, and anything not listed below

auxiliary:
  title:
    model: claude-haiku-4-5-20251001    # naming a session is trivial — use something cheap
  summarize:
    model: claude-haiku-4-5-20251001
  judge:
    model: openai:gpt-4o-mini           # a different provider entirely is fine
    api_key: sk-...                     # and its own key, if you like
```

**For one run only**, without editing anything:

```bash
any2wiki chat "hi" -m openai:gpt-4o           # every task not pinned above
ANY2WIKI_MODEL_JUDGE=openai:gpt-4o any2wiki config show   # one task
```

> **The shipped** `config.yaml` **already pins five tasks to** `claude-haiku-4-5` — cheap
> models for cheap work. That is why `config show` shows haiku for everything except the
> supervisor, and why `-m` appears to move only the supervisor: a task pinned in
> `config.yaml` beats the flag. Delete those `auxiliary` entries if you want one model
> everywhere.



### Which models can be the supervisor

`supervisor` is the only task that needs a strong model. It runs a loop: read a skill, list files, search, read the right pages, decide what is missing, write. That is 2–15 dependent tool calls, each one conditioned on the last, with skills, wiki pages and tool output all in context at once. The other five tasks are one short call each, so cheap models are the right choice there.

Pick the supervisor for multi-step tool routing and sound reasoning under a large context. Coding benchmarks are secondary; function-calling accuracy (BFCL) and long-context stability matter more.

**Suitable supervisors**

```yaml
# Anthropic
anthropic:claude-sonnet-5             # default pick; 1M ctx, $3/$15
anthropic:claude-opus-5               # escalation; 1M ctx, $5/$25
anthropic:claude-sonnet-4-6           # current; 1M ctx, $3/$15. Keep only for pinning
anthropic:claude-opus-4-8             # $5/$25, SWE-bench Pro 69.2; same price as Opus 5
anthropic:claude-opus-4-7             # $5/$25, BFCL v3 76.6% (2nd overall, June 2026)
anthropic:claude-opus-4-6             # $5/$25, 1M ctx; older, still reliable tool loops
anthropic:claude-sonnet-4-5-20250929  # 200k ctx, $3/$15, BFCL 73.2%. Fine if 200k is enough
anthropic:claude-opus-4-5-20251101    # 200k ctx, $5/$25, BFCL 77.5% on one tracker

# OpenAI 
openai:gpt-6-astra                    # $10/$50; strong but 2x Opus price, cache read $1
openai:gpt-5.5                        # $5/$30; SEAL SWE-bench Pro leader in June
openai:gpt-5.4                        # $2.5/$15; cheapest OpenAI with 1M ctx

# Google
google_genai:gemini-3.1-pro-preview   # note the -preview suffix; the bare name does not resolve

# Open weights via OpenRouter
openrouter:qwen/qwen3.7-max           # BFCL-V4 leader 75.0%, $1.25/$3.75; RL base family
openrouter:qwen/qwen3.5-397b-a17b     # BFCL-V4 72.9%, top open model before 3.7
openrouter:qwen/qwen3-32b             # BFCL v3 75.7% at $0.08/$0.28; fits one GPU
openrouter:z-ai/glm-4.5               # BFCL v3 76.7% (topped it in June), $0.60/$2.20
openrouter:z-ai/glm-5.2               # 744B/40B active, GPQA 91.2
openrouter:moonshotai/kimi-k3         # 2.8T/~50B, GPQA 93.5; reasoning over tool use
openrouter:deepseek/deepseek-v4-pro   # $0.43/$0.87, SWE-bench 80.6; cheapest strong option
openrouter:deepseek/deepseek-v3.2     # cheap; too weak for code, OK for routing only

```

**Not suitable as supervisor** (use for the five single-call tasks instead)

```yaml
anthropic:claude-haiku-4-5-20251001   # 200k ctx, BFCL 68.7
openrouter:deepseek/deepseek-v4-flash # 13B active; bulk inference and RL base
openrouter:google/gemini-3.8-flash    # no agentic benchmarks yet
openrouter:google/gemini-2.5-flash    # BFCL 56.2
openrouter:moonshotai/kimi-k2.5       # BFCL 47.1
openrouter:meta-llama/llama-4-maverick  # mid on both BFCL and SWE
openrouter:meta-llama/llama-4-scout
openrouter:mistralai/mistral-large-2512

```

---



## Quick start

Pick one model, set that provider's key, done. Everything else here is for when you want
one task to differ, or a non-default endpoint.

```yaml
# config.yaml
model:
  default: claude-sonnet-4-6
```

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
```

```bash
any2wiki config show      # confirm before running anything
```

---



## Provider recipes

Each block goes in `config.yaml`. After each one, run `any2wiki config show` and check
the **Provider** and **Endpoint** columns say what you expect.

### Anthropic

```yaml
model:
  default: claude-sonnet-4-6
```

```bash
ANTHROPIC_API_KEY=sk-ant-...
```



### OpenAI

```yaml
model:
  default: openai:gpt-4o
```

```bash
OPENAI_API_KEY=sk-...
```



### Google Gemini

```yaml
model:
  default: google_genai:gemini-3.5-flash-lite
```

```bash
GOOGLE_API_KEY=...
```

To check what your key can actually reach, run:

```bash
uv run --env-file .env python -c "
import os, urllib.request, json
d = json.load(urllib.request.urlopen(
    f\"https://generativelanguage.googleapis.com/v1beta/models?key={os.environ['GOOGLE_API_KEY']}\"))
print(*sorted(m['name'].replace('models/','') for m in d['models']
              if 'generateContent' in m.get('supportedGenerationMethods',[])), sep='\n')"
```



### OpenRouter — one key, most models

OpenRouter is OpenAI-compatible, so it is `provider: openai` plus a `base_url`. **No extra
package to install.**

```yaml
model:
  default: anthropic/claude-sonnet-4.5   # OpenRouter uses provider/model with a slash
  provider: openai
  base_url: https://openrouter.ai/api/v1
  api_key: sk-or-...
```

`config show` should read:

```
supervisor  anthropic/claude-sonnet-4.5  openai  https://openrouter.ai/api/v1
```

That row is the whole point of the endpoint column: the model is a Claude model, but the
request goes to OpenRouter, not to Anthropic.

Switch models within OpenRouter without editing the file:

```bash
any2wiki chat "hi" -m openai/gpt-4o
any2wiki chat "hi" -m google/gemini-2.5-flash
```



### Ollama — local

First pull a model that runs on your machine:

```bash
ollama pull llama3.2
ollama list          # confirm it is there and NOT a ":cloud" entry
```

```yaml
model:
  default: llama3.2
  provider: openai                       # Ollama serves an OpenAI-compatible API
  base_url: http://localhost:11434/v1
  api_key: ollama                        # required by the client, ignored by the server
```

No key, no cost, works offline. `ollama serve` must be running.

### Ollama Cloud

Models listed as `something:cloud` do **not** run locally — they run on ollama.com and need
a key.

```yaml
model:
  default: qwen3.5:cloud
  provider: openai
  base_url: https://ollama.com/v1
  api_key: <your ollama.com key>
```

> The `:cloud` suffix is a **model tag**, not a `provider:model` prefix. `qwen3.5` is not a
> provider name, so it is left alone — see *Troubleshooting* below for when a colon **is**
> treated as a provider.



### LiteLLM gateway

If you run the optional proxy in `gateway/`, route through it with an env var instead of
config:

```bash
ANY2WIKI_LLM_GATEWAY=litellm
LITELLM_BASE_URL=http://localhost:4000     # optional, this is the default
LITELLM_API_KEY=sk-virtual-key-...
```

Every task then goes to the proxy, which handles the real provider keys, budgets and
fallbacks. See `gateway/README.md`.

---



## Which model a task ends up using

Five levels. **The first one that exists wins:**

```
Task-Specific Env Var → Task Config → Global Env Var → Base Config → Default Fallback
```


| Level                         | Where           | Example                                         | Applies to |
| ----------------------------- | --------------- | ----------------------------------------------- | ---------- |
| **1 · Task-Specific Env Var** | `.env`          | `ANY2WIKI_MODEL_SUMMARIZE=openai:gpt-4o-mini`   | one task   |
| **2 · Task Config**           | `config.yaml`   | `auxiliary.summarize.model: openai:gpt-4o-mini` | one task   |
| **3 · Global Env Var**        | `.env`, or `-m` | `ANY2WIKI_MODEL=openai:gpt-4o`                  | every task |
| **4 · Base Config**           | `config.yaml`   | `model.default: openai:gpt-4o`                  | every task |
| **5 · Default Fallback**      | built in        | `claude-sonnet-4-6`                             | every task |


The pattern: **task beats global, and env beats config.**

The six tasks are listed at the top of this document.

### The `-m` / `--model` flag

`-m` writes `ANY2WIKI_MODEL` for that one run, so it lands at **level 3**.

```bash
any2wiki repl -m openai:gpt-4o
any2wiki chat "summarise this" -m openai:gpt-4o
any2wiki config show -m openai:gpt-4o        # preview only, no API call
any2wiki serve -m openai:gpt-4o
```

It must come **after** a command — `any2wiki -m openai:gpt-4o` alone is an error.

**It does not override a task pinned in** `config.yaml`**.** With `auxiliary.judge.model` set,
`-m` moves every other task and leaves `judge` alone:

```bash
any2wiki config show -m openai:gpt-4o
#   supervisor  openai:gpt-4o              ← the flag
#   judge       claude-haiku-4-5-20251001  ← auxiliary.judge.model won
```

That is deliberate, and copied from hermes-agent: side tasks are pinned for a reason —
cheap summarisation, vision — and one flag silently retargeting them would break them.
To change a pinned task too, use its own env var:

```bash
ANY2WIKI_MODEL_JUDGE=openai:gpt-4o any2wiki config show -m openai:gpt-4o
```

`-m` **sets only the model, never the endpoint.** With OpenRouter configured, `-m` switches
models *within* OpenRouter. To change endpoint, edit `config.yaml`.

---



## Per-task models

Any task can have its own model, provider, endpoint and key:

```yaml
model:
  default: claude-sonnet-4-6            # the supervisor: the model that does the thinking

auxiliary:
  title:                                 # naming a session — trivial, use something cheap
    model: claude-haiku-4-5-20251001
  summarize:
    model: claude-haiku-4-5-20251001
  judge:                                 # eval judge — can be a different provider entirely
    model: openai:gpt-4o-mini
    api_key: sk-...                      # its own key, if you like
```

Which fields inherit from the `model:` block when a task omits them:


| field        | inherits?          |
| ------------ | ------------------ |
| `model`      | yes                |
| `provider`   | yes                |
| `base_url`   | yes                |
| `api_key`    | yes                |
| `timeout`    | **no** — task-only |
| `extra_body` | **no** — task-only |


Setting `model.timeout` does not give it to the tasks; only a task's own block does.

---



## Checking without spending anything

`config show` reads config the same way a run does, so it is a free dry run. Preview an
override before committing to it:

```bash
any2wiki config show                                  # what runs today
any2wiki config show -m openai:gpt-4o                 # what the flag would change
ANY2WIKI_CONFIG=/tmp/try.yaml any2wiki config show  # try a whole config, safely
```

`ANY2WIKI_CONFIG` points at any file, so you can test a config without touching your real
one:

```bash
TMP=$(mktemp -d)
cat > "$TMP/c.yaml" <<'YAML'
model:
  default: anthropic/claude-sonnet-4.5
  provider: openai
  base_url: https://openrouter.ai/api/v1
YAML
ANY2WIKI_CONFIG=$TMP/c.yaml any2wiki config show
```

Read the **Provider** and **Endpoint** columns, not just the model. `provider default`
means the provider's own API; anything else is where your requests are really going.

---



## Troubleshooting



### `404 not_found_error — model: openai:gpt-4o`

The request went to the **wrong provider**. The error comes from Anthropic, complaining
about a model name that is obviously OpenAI's — meaning the provider was pinned to
`anthropic` while the model said `openai`.

Check the Provider column:

```bash
any2wiki config show
```

If Model and Provider disagree, one of them is wrong. An explicit `provider:` prefix in the
model string now wins over `model.provider` in config, so this should not recur — but a
stale `provider:` line in `config.yaml` is still worth removing if you have switched
providers.

### `The api_key client option must be set`

The provider's key is missing from `.env`. Which key depends on the model, not on Anthropic:


| model looks like             | needs                              |
| ---------------------------- | ---------------------------------- |
| `claude-…`, `anthropic:…`    | `ANTHROPIC_API_KEY`                |
| `gpt-…`, `openai:…`          | `OPENAI_API_KEY`                   |
| `gemini-…`, `google_genai:…` | `GOOGLE_API_KEY`                   |
| `groq:…`                     | `GROQ_API_KEY`                     |
| anything with a `base_url`   | that endpoint's key, in `api_key:` |




### `insufficient_quota` / `credit_balance_exhausted`

Routing is correct — the account is out of credit. This error naming the right provider is
actually a good sign.

### `ModuleNotFoundError: No module named 'langchain_ollama'`

Native Ollama support is not installed. Use the OpenAI-compatible recipe above
(`provider: openai` + `base_url`) — no extra package needed. Or `uv add langchain-ollama`
if you would rather use `ollama:model` directly.

### `Unable to infer model provider`

The model name matches no known provider and none was configured. Either use the
`provider:model` form (`openai:gpt-4o`) or set `provider:` explicitly.

### A task ignores `-m`

It has its own `auxiliary.<task>.model`. Expected — see the flag section above. Override it
with `ANY2WIKI_MODEL_<TASK>`, or remove the pin from `config.yaml`.

---



## Related

- `README.md` → **Using the CLI** — every command and flag
- `config.example.yaml` — every option, commented
- `gateway/README.md` — the optional LiteLLM proxy
- `src/llm_roles.py` — the resolver, if you want the exact rules in code

