# Costs and budget controls

Prices checked on 2026-11-25. They change; update `config/settings.yaml → pricing` when they do.

## LLM options (USD per million tokens)

| Model | Input | Output | Notes |
|---|---|---|---|
| **Claude Haiku 5.5** (`claude-haiku-5-5`) — default | 0.10 | 0.50 | Prompts up to 100K tokens; structured JSON output supported. Anthropic pricing table. |
| Gemini 3.5 Flash-Lite (`gemini-3.5-flash-lite`) | 0.30 | 2.50 | Gemini 2.5 Flash-Lite now returns "no longer available to new users" (seen 2026-11-25). Called via Google's OpenAI-compatible endpoint with a Bearer key. |
| GPT-5 nano | 0.05 | 0.40 | OpenAI model page. |
| GPT-5 mini | 0.25 | 2.00 | Third-party trackers. |

Haiku 5.5 and GPT-5 nano cost a few dollars a month at this volume. Gemini 3.5 Flash-Lite costs
roughly 3–5× as much per call (about $10–$18 a month at default settings), which can exceed
the ₹1,500 cap. Haiku 5.5 is the default because it supports schema-constrained JSON output, which
cuts malformed responses, and it reads long pages well. Switch with the `LLM_PROVIDER` variable;
no code changes.

When the main model keeps answering "overloaded" (HTTP 503) or rate-limited (429), the engine
switches to the model in `llm.fallback_models` (for Gemini: `gemini-3.5-flash`) for the rest of
the run. A model with no entry under `pricing` is costed at a conservative $1/$5 per million
tokens, so the budget tracker errs high.

## Search options

| Provider | Price | Free allowance | Notes |
|---|---|---|---|
| **Brave Search API** — default | $5 per 1,000 queries | $5 credit per month (~1,000 queries); card required | Independent index; web + news endpoints; the free plan was replaced by monthly credit in 2026. |
| Serper (Google results) | ~$1 per 1,000 (50K pack for $50) | 2,500 queries once, no card | Cheapest per query, but the smallest pack ($50) exceeds one month's budget; credits expire after ~6 months. |
| Google Programmable Search JSON API | — | — | Reported closed to new customers; not implemented. |
| Free sources (always on) | $0 | — | TechCrunch/EU-Startups/VentureBeat/Tech in Asia/Inc42 RSS, Google News RSS, Hacker News (Algolia), Product Hunt API (token), direct site fetches. |

Recommendation: start with Brave. If coverage is too thin later, Serper is the cheapest upgrade
once you are ready to prepay $50. Neither is bought automatically.

For future Reddit-specific research, either provider can run `site:reddit.com` queries through
the same `SearchProvider` interface. Add a subclass in `providers/search_provider.py`.

## Monthly estimate at default settings

Up to 60 companies researched and 50 search queries a day, to keep the list at 15 leads.

| Item | Per day | Per month (30 days) |
|---|---|---|
| Search: ≤ 50 Brave queries | ≤ $0.25 | ~1,500 queries ≈ $7.50, minus Brave's $5 credit ≈ **$2.50 (₹220)** |
| LLM, Claude Haiku 5.5: ~60 research + ~15 discovery calls | ~$0.25 | **~$7.50 (₹660)** |
| GitHub Actions, Google Sheets, Gmail | $0 | $0 |
| **Total** | | **≈ ₹800–₹950**, hard cap ₹1,500 |

## Controls in the code

- `budget.monthly_budget_inr: 1500` (converted at `inr_per_usd: 88`).
- Month-to-date spend = sum of "Estimated API Cost (USD)" in the Daily Run Log for the month.
  The tracker counts gross list price and ignores free credits, so it errs high.
- ≥ 80%: reduced mode (20 candidates, 25 queries, fewer discovery searches).
- ≥ 100%: no paid calls; the run stops before research and sends a notice email.
- Per-run caps regardless of budget: `search.max_queries_per_run: 50`, `llm.max_calls_per_run: 120`.
- Caching: search results 14 days, pages 7 days, LLM responses 30 days, persisted between runs
  with `actions/cache`, so retries and re-discoveries cost little.
- Unknown model names are priced conservatively at $1/$5 per million tokens.
