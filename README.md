# emporio-agent

A text-message customer-service agent for **Empório da Música**, a fictional
musical-instrument store in Campo Grande, MS. Built for the Artefact AI
Engineer technical challenge.

The agent (persona "Tom") answers in Brazilian Portuguese over a CLI chat,
using OpenAI-style function calling against seven tools backed by the
store's own CSV data and policy manual -- never by the model's own
"knowledge" of prices, stock, or rules.

## Architecture

```
                 ┌─────────────────────────────────────┐
 user message →  │  cli.py  (read-eval-print loop)      │
                 └───────────────┬───────────────────────┘
                                 │
                                 ▼
                 ┌─────────────────────────────────────┐
                 │  agent.py: run_turn()                │
                 │  - builds system prompt (prompt.py)  │
                 │  - [system] + history window + user   │
                 │  - calls chat.completions.create()    │
                 │  - loop ≤ 6 rounds while tool_calls    │
                 └───────┬───────────────────┬───────────┘
                         │                   │
                model decides WHEN   code decides WHAT'S ALLOWED
                         │                   │
                         ▼                   ▼
                 ┌──────────────┐   ┌──────────────────────────┐
                 │ LLM (OpenAI- │   │ tools.py: run_tool()      │
                 │ compatible)  │   │  ├─ search_products        │
                 └──────────────┘   │  ├─ get_payment_options    │
                                    │  ├─ lookup_order            │
                                    │  ├─ check_return_eligibility│
                                    │  ├─ search_policies         │
                                    │  ├─ get_shipping_info       │
                                    │  └─ escalate_to_human       │
                                    └───────┬──────────┬──────────┘
                                            ▼          ▼
                                   ┌────────────┐ ┌────────────┐
                                   │ data.py /  │ │ policies.py│
                                   │ rules.py   │ │ (BM25 over │
                                   │ (CSV, in   │ │ manual     │
                                   │ memory)    │ │ chunks)    │
                                   └────────────┘ └────────────┘

session.py persists every turn to .sessions/<id>.json (resumable with
--session). handoffs.jsonl is the human-handoff "CRM" escalate_to_human
writes to.
```

The guiding principle: **the model decides *when* to call a tool; the code
decides *what is allowed* and does all arithmetic/date math.** Prices,
stock, installment eligibility, store hours, and return-window deadlines
are all computed in plain Python (`rules.py`, `data.py`) -- the LLM only
ever sees the result and phrases the answer. This is also where privacy is
enforced: `lookup_order` never returns the customer's full name, phone, or
email to the model, regardless of what the prompt says -- it's enforced in
code, not just requested of the model (see `tests/test_agent.py::test_privacy_enforced_in_code_not_just_prompt`).

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env with your LLM_API_KEY (see "Providers" below for free options)

python -m emporio_agent                 # start a new chat
python -m emporio_agent --session abc123 # resume a previous session
python -m emporio_agent --debug          # also print each tool call + result

pytest -q                                # run the test suite (no network, no API key needed)
```

To regenerate `data/policies_chunks.json` after editing the policy PDF
(requires the `pdftotext` CLI from poppler-utils):

```bash
python scripts/ingest_policies.py
```

To regenerate `examples/*.md` against the real configured LLM:

```bash
python scripts/record_scenarios.py
```

### Providers

Any OpenAI-compatible `/chat/completions` endpoint works -- just set three
env vars. Default is Gemini 2.5 Flash because it has a genuinely free tier,
so anyone evaluating this can run it at zero cost.

| Provider | `LLM_BASE_URL` | `LLM_MODEL` | Notes |
|---|---|---|---|
| **Google Gemini (default)** | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` | Free tier, key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | Paid |
| Ollama (local) | `http://localhost:11434/v1` | any pulled model, e.g. `llama3.1` | Free, no key needed (use any placeholder string), but local tool-calling quality varies by model |

## Technical decisions

**Framework / approach -- function calling, not RAG/text-to-SQL/ReAct.**
The data here is small and heterogeneous (structured CSV rows + an 8-page
PDF), and the required behavior is "know which tool to use," not "retrieve
and summarize long documents." Plain function calling is the simplest
thing that satisfies the brief: the model's only real job is routing a
message to 0-N of seven well-typed tools, and every tool already returns a
clean, final answer the model just has to phrase. A RAG-only design would
force policy *and* catalog facts through the same embedding-retrieval
pipeline, which is a bad fit for exact price/stock lookups (retrieval is
inherently fuzzy; a price isn't). Text-to-SQL is overkill for CSVs this
small and adds a failure mode (bad SQL) with no real benefit over direct
Python filtering. ReAct/agent frameworks (LangChain, etc.) add a
dependency and an abstraction layer for a loop that's ~40 lines of plain
Python here -- not worth it at this scale, and it would obscure exactly
the decision logic this challenge is evaluating.

**Model / provider -- Gemini 2.5 Flash via its OpenAI-compatible endpoint,
temperature 0.3.** Chosen for being free, fast, and good enough at
structured tool calling; the OpenAI SDK against an OpenAI-compatible
`base_url` means swapping to OpenAI or a local Ollama model is a 3-line
`.env` change, not a code change. Temperature 0.3 keeps phrasing natural
but discourages creative drift on anything numeric.

**Retrieval -- hand-rolled BM25, no embeddings.** The policy manual is
~4,000 tokens across 28 sections after ingestion. An embeddings/vector-store
pipeline is the wrong tool for a corpus this small: it adds an external
dependency, non-determinism, and real latency/cost for a problem that a
~150-line BM25 implementation with light PT stemming, a stopword list, and
a domain synonym map (e.g. "devolver" → "arrependimento") solves
deterministically and for free. Retrieval returns whole sections (never
truncated snippets) plus the section number, so the agent can both answer
precisely and cite where the rule comes from. A query that matches nothing
returns an empty list -- the prompt instructs the agent to say it doesn't
know and offer the human team, rather than invent a policy.

**Prompt strategy -- rebuilt every turn, numbered rules, persona-first.**
`prompt.py` regenerates the system prompt on every turn with the current
date/time and open/closed status (computed by `rules.store_status`,
never guessed by the model), so "are you open now?" is always answered
against the real clock. The persona ("Tom") and ~13 numbered rules are
designed to be *testable*: each rule maps to something a tool result can
carry (a `flags` list, a `confidence` field, an `escalate` flag) rather
than asking the model to reason about raw data itself.

**Security / privacy -- enforced in code, not just prompted.** Three
load-bearing examples: (1) `OrderBook.verify()` identifies a customer only
by email or last-9-digits-of-phone matching the order's actual customer --
never by name, since the dataset has duplicate names and two customers
(11 and 43) sharing one email; (2) `order_summary()` never includes phone
or email, and `Product.to_public()` never includes exact stock counts;
(3) `check_return_eligibility` hard-refuses to run unless `lookup_order`
already verified that *order_id* earlier in the *same session*
(`Session.verified_orders`) -- a prompt instruction alone could be talked
around, a code-level gate can't.

**Interface / persistence -- CLI + per-session JSON files.** A CLI is the
fastest way to demonstrate a working agent without building and
maintaining a web UI, which the brief explicitly says isn't the point.
Each session is one JSON file in `.sessions/<id>.json`, rewritten after
every turn, so a conversation survives a restart (`--session ID`) --
useful for the multi-turn return-eligibility flow, which can legitimately
span several messages. Only the last 40 messages are ever sent back to the
model (trimmed to the nearest `user`-message boundary so a tool_call/tool
pair is never split); the full history stays on disk.

**Data handling.**

| Concern | Where | What happens |
|---|---|---|
| Stock vs. status | `data.Product.availability` | `discontinued`/`coming_soon` win over stock count; `stock<=0` → `out_of_stock` even if status is `active`; `stock<=2` → `low_stock`; exact count never exposed |
| Promotions | `data.Catalog` (load time) | Only `is_active=1` rows counted; highest discount wins if several are active; expired promos ignored entirely |
| Fuzzy product search | `data.name_matches` | difflib-based typo tolerance + adjacent-token merging ("gd 20" ≈ "GD20"), but any query token containing a digit must match *exactly* -- so "GF-3D" can never fuzzy-match "GF-1R" |
| Customer identity | `data.OrderBook.verify` | Email (case-insensitive) or last 9 phone digits must match the order's actual customer; name is never used, and a wrong contact and a nonexistent order return the identical error |
| Data-quality issues | `data.OrderBook.order_summary` | Emits a `flags` list (`total_mismatch`, `overdue_shipment`, `not_yet_shipped`) instead of silently trusting `total_brl` / dates |
| Return-date uncertainty | `rules.return_check` | The dataset only has an *estimated* delivery date, not a real receipt date; the result always says `received_date_is_estimate` and a `confidence` level, and the prompt tells the agent to ask the customer to confirm in borderline cases |

## Assumptions

Documented here because the brief explicitly invites reasonable
assumptions over blocking on ambiguity. See `scripts/ingest_policies.py`'s
`NOTES` dict for the same notes attached directly to the relevant policy
chunks.

- **Contact phone/WhatsApp:** the manual's cover page and §1.2 both say
  `(67) 3341-4444`; §7 says `(67) 3321-4500`. Treated `3341-4444` as correct
  (stated twice, including the cover) and `3321-4500` as a typo.
- **Contact e-mail:** §1.2 prints `contato@empóriodamusica.com.br` (with an
  accented ó), which isn't a valid/registrable domain. Used
  `contato@emporiodamusica.com.br` (no accent, matching the cover page).
- **Installment minimums:** §3's single-row table ("up to 12x, min.
  R$100") is treated as only describing the top tier; §3.1's three tiers
  (≤3x no real minimum / 4-6x ≥R$80 / 7-12x ≥R$100) are the actual rule
  applied by `get_payment_options`.
- **Free shipping threshold:** "free for orders above R$500" is read as
  *strictly* greater than R$500 -- a R$500.00 order pays the R$35 flat fee.
- **"Metropolitan region":** the manual never defines it, so only the city
  of Campo Grande itself is treated as "local" delivery; every other city
  (including ones genuinely near Campo Grande) uses the "other cities"
  rule (PAC/SEDEX/Jadlog, no invented price -- it's calculated by CEP).
- **30 vs. 90 day defect window:** §4.2 gives 30 days *from purchase* for
  a direct exchange; §8.1 gives 90 days *from receipt* as legal warranty.
  Between the two, `return_check` returns `escalate: true` rather than
  picking a winner -- that gap is exactly what a human should decide.
- **Right of withdrawal assumes an online purchase** when the tool isn't
  told otherwise (`is_online_purchase=None` → assumed `True`), since this
  channel (text-message agent) is itself a remote/online channel and the
  dataset doesn't record purchase channel at all. The response flags
  `assumed_online_purchase: true` so the agent can double-check if the
  customer says otherwise.
- **Catalog scope:** the manual claims "300+ instruments" across 9
  categories; the actual data has 65 products across 5 categories
  (nothing in Instrumentos de Sopro, Cordas Orquestrais). The agent only
  ever asserts what `search_products` actually returns, and is instructed
  to say the system doesn't show stock for a missing category rather than
  claim the store doesn't carry it at all.
- **"Now" is simulated:** the order dataset reads like a snapshot from
  around March 2026 (e.g. order dates, "overdue" shipment logic), while the
  actual delivery date of this project is November 2026. `AGENT_NOW`
  freezes the clock for tests and for `scripts/record_scenarios.py` so the
  examples are reproducible and consistent with the data's own timeline.
- **`strings` search filter** maps directly to the `specs.strings` field,
  which is `"nylon"`/`"steel"` for violões/ukuleles. Electric guitars/basses
  use `specs.strings` for a *string count* instead (e.g. `"6"`), so the
  filter is documented and intended for the acoustic-instrument case the
  brief's own examples use.

## Known limitations / next steps

- **No LLM-judge eval suite.** The test suite pins deterministic logic
  (rules, data, retrieval, the agent loop with a scripted fake LLM) but
  there's no automated scoring of real model *responses* for tone/
  correctness drift. With more time: a small eval harness that runs fixed
  prompts against the real model and scores the answer with a second LLM
  call against a rubric (did it cite a price? did it avoid promising a
  discount? etc.).
- **Identity verification is email/phone string-matching**, which is fine
  for a prototype but not WhatsApp-grade. A real deployment would arrive
  via a WhatsApp webhook where the *phone number is the channel itself*,
  so identity could be established once via OTP and trusted for the
  session, instead of asking for it conversationally every time.
- **`handoffs.jsonl` is a stand-in for a CRM.** Fine for a prototype;
  a real one needs a ticket ID back to the customer, retry/at-least-once
  delivery, and a notification channel for the human team (today it's
  just an append-only file nobody is watching).
- **BM25 has no semantic generalization** beyond the synonym map I wrote
  by hand. It's a deliberate, documented trade-off for this manual's size
  (see "Technical decisions" above), but it would not scale to a much
  larger or more linguistically varied policy document without either a
  bigger synonym map or switching to embeddings.
- **In-memory CSV loading** doesn't scale past "small shop prototype" --
  a real deployment would put this in Postgres (or similar) so stock/price
  updates don't require a redeploy, and so multiple agent processes share
  one consistent view of the data.
- **No observability.** Tool calls and escalations are visible via
  `--debug` and `handoffs.jsonl`, but there's no structured logging,
  tracing, or metrics on latency/tool-error-rate/escalation-rate -- all of
  which matter the moment this handles real traffic.
- **Special hours aren't modeled.** §2 of the manual mentions extended
  hours for Black Friday, the store's anniversary, and Christmas, but
  gives no actual schedule for them, so `rules.store_status` doesn't
  account for them. Would need the store to supply a real calendar of
  exceptions.

## Use of AI coding assistants

I used **Claude Code** (Anthropic's CLI agent) as a collaborator, not as
the sole author of the implementation. I wrote the Portuguese brief
describing the architecture, file layout, and every business rule in
detail, and implemented the project's modules myself from that brief.
Claude Code's responsibility was narrower and concentrated on two areas:

- **Architecture.** It helped design the complete project architecture
  up front -- the module breakdown (`config.py` through `cli.py`), the
  PDF-ingestion and BM25 retrieval approach, and the overall file
  layout -- before any implementation started.
- **Tests and ad-hoc verification.** It wrote the `pytest` suite, and
  ran the test suite and ad-hoc verification scripts continuously during
  development (e.g. verifying every claimed data "gotcha" -- the
  GF-3D/out-of-stock product, the duplicate customer email, the two
  orders with mismatched totals -- by running real Python against the
  data, and catching a synonym-mapping bug in the BM25 index that made
  "que horas vocês abrem?" miss the opening-hours section).

<!-- Gustavo: add a line here on what you personally reviewed, changed, or
     would have done differently, once you've gone through the diff. -->

## Folder layout

```
pyproject.toml          Package metadata + dependencies
.env.example            Provider configuration template
data/                    Original CSVs + policy PDF + generated policies_chunks.json
src/emporio_agent/
  config.py              Paths, timezone, freezable clock (AGENT_NOW)
  data.py                CSV loading, fuzzy search, order verification
  rules.py               Store hours, payments, shipping, returns
  policies.py            BM25 retrieval over policies_chunks.json
  tools.py               7 tool schemas + dispatch
  prompt.py              Persona + rules, rebuilt every turn
  agent.py               The function-calling loop
  session.py             Per-conversation JSON persistence
  cli.py / __main__.py    CLI entrypoint
scripts/
  ingest_policies.py      PDF → data/policies_chunks.json
  record_scenarios.py     Runs real scenarios → examples/*.md
tests/                   pytest suite (no network -- fake LLM for agent.py)
examples/                 3-5 real recorded conversations
```
