# Provider and production assessment

Documentation checked October 26, 2026. This is a deployment decision guide; no live provider benchmark has been established by the mocked tests. Recheck model availability and your account dashboard before deployment.

| Property | OpenAI variant | Cohere variant |
| --- | --- | --- |
| Default generation | `gpt-4.1-mini` | `command-a-03-2025` |
| Document and query embeddings | `text-embedding-3-small` | `embed-v4.0`, separate `search_document` / `search_query` input types |
| Published generation context | 1,047,576 tokens | 256,000 tokens |
| Published maximum output | 32,768 tokens | 8,000 tokens |
| App's generation output cap | 4,096 tokens, configurable | 4,096 tokens, configurable |
| Generation price per million tokens | $0.40 input / $1.60 output; cached input differs | $2.50 input / $10 output |
| Throttling | Model/account/tier-specific requests and tokens per minute; inspect account limits and returned headers | Command A: 20 requests/minute trial, 500 production; Embed: 2,000 inputs/minute in the documented table |
| Trial restrictions | Access and quota depend on the account; do not assume free credit | Trial keys capped at 1,000 API calls/month; newer model families may require sales approval even on production keys |

Generation limits and prices: [official OpenAI GPT-4.1 mini documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [Cohere Command A documentation](https://docs.cohere.com/docs/command-a). These are selected, configurable defaults, not a claim that either is the latest or best model.

OpenAI embedding inputs are limited to 8,192 tokens per input in its model guide. The app conservatively chunks by characters, batches 64 inputs, and does not silently truncate Cohere input. Cohere documents a 96-text maximum per embedding call. See [OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings) and [Cohere Embed API](https://docs.cohere.com/v2/reference/embed). Model changes require new vectors; indexes are keyed by provider and embedding model.

Rate limits are separate from context and output limits. OpenAI's request/token ceilings depend on model and usage tier, so no single global rate is asserted here. Cohere's trial and production ceilings differ by endpoint and model. See [OpenAI rate-limit guide](https://developers.openai.com/api/docs/guides/rate-limits) and [Cohere key types and limits](https://docs.cohere.com/v2/docs/rate-limits). Runtime telemetry captures available limit headers, HTTP 429, attempt count, and API usage. Account dashboards remain authoritative; absent headers do not mean unlimited usage.

## What each enables

OpenAI's chosen model has a larger documented context and lower listed generation token prices than the chosen Cohere model. That can enable longer prompts and lower generation spend at equivalent token counts, but neither latency nor tax accuracy follows from those specifications. The app currently applies smaller contract limits, so the larger model context is not fully used. Evaluate larger section-based analysis before relaxing those limits.

Cohere provides explicit search document/query embedding modes and a dedicated enterprise-oriented generation model. The app uses those embedding modes, but does not yet use Cohere Rerank. The trial chat ceiling can substantially constrain clause analysis: tax analysis makes a generation call for each locally segmented clause/section, plus per-section query embeddings in source-grounded mode. It does not make contract-summary or AI clause-extraction calls. A single large analysis can therefore exceed a trial minute's chat allowance. Production keys increase throughput, subject to the documented model limits.

Both providers support the implemented English/Arabic text workflows. Which produces better Arabic tax answers must be assessed on your own source corpus. Similarity scores are retrieval ranking signals, not calibrated answer confidence, and cannot be compared numerically across embedding models. The UI exposes retrieved passages so reviewers can inspect evidence.

## Measure before choosing

1. Run the assessment with both real keys and a fixed case set. Compare successful-case p50/p95 and errors, then inspect per-step timings to distinguish extraction, cold indexing, query embeddings, retrieval, generation, and export.
2. Separate cold indexing from warm question latency. Add at least dozens of repeats and real bilingual documents; five samples are a smoke benchmark, not a production percentile estimate.
3. Score the blind review sheet with qualified tax reviewers. Check exact contract quotes, omitted material changes, citation support, Arabic clarity, correct abstention when evidence is absent, and consistency across runs. Keyword coverage and citation syntax alone do not establish correctness. Contract comparison validates quoted snippets against source text; tax analysis uses deterministic exact-text sections rather than model-extracted clauses.
4. Inspect `usage.csv`: input/output tokens, billed units, output-limit failures, rate-limit headers, and retry counts. Multiply provider billed units by current prices, including embeddings and re-indexing. Token counts differ across providers; compare spend per successful task as well as tokens. No automatic dollar estimates are supplied because model prices and account discounts vary.
5. Add concurrency tests using the deployed HTTP service. The script uses Flask's test client with real outbound API calls, so it measures the processing pipeline but excludes browser/network/server-worker queuing. It does not prove production throughput.

## Current app boundaries

This implementation is a local/single-workspace application. It is not ready for a public multi-tenant launch. Authentication, authorization, tenant separation, abuse limits, encrypted storage/backup policies, data-retention controls, and audit access must be designed before public exposure. Provider selection is a request header, not an access-control boundary. All users of one server share the document library and dictionary.

SQLite plus NumPy cosine search provides simple persistent retrieval suitable for a modest local corpus. Retrieval scans stored vectors; migrate to a vector database with document-versioned indexing for large corpora. Concurrent upload/replace operations can race with lazy index builds; use revision checks/background jobs before high-concurrency deployment. The dictionary is a shared JSON file protected by a file lock and atomic writes. Each run reads a fresh snapshot; local workers share the same file.

Generation and OCR are synchronous. Use a worker queue, task cancellation, live server progress events, bounded OCR page counts, and a job status API for long contracts and large scanned documents. The live browser timer shows request elapsed time; completed per-step timings arrive in the final response. Retries cover 429 and transient 5xx up to three attempts, with a capped Retry-After delay; there is no distributed rate limiter or circuit breaker. Connection failures/timeouts return an error without retrying a potentially charged generation request.

Tax clause analysis offers a source-grounded mode that retrieves passages only from explicitly selected Tax AI Chat library documents for each clause. It reports cited passages and evidence gaps, with undetermined risk when evidence is insufficient. General mode still uses model knowledge without reference retrieval. The exact extracted contract text is analyzed in local sections after confidential-term dictionary replacements; no contract summary is generated or used. Citation validation checks passage identity and presence, not the legal correctness or entailment of the claims. Treat both modes as analytical drafts. Chat is grounded in uploaded sources, which can be stale; the app does not verify current tax law online. The model's structured JSON and quote checks improve traceability, but do not establish tax/legal correctness.

The root application deliberately removes the legacy arbitrary server-folder scanner and disallows client-chosen export directories. Keys stay server-side. Runtime logs omit source content and secrets, but assessment exports intentionally include answers and retrieved passages: protect and expire them. A privacy/residency review must establish whether the global public endpoints, contract terms, retention, and regional processing meet your organization's requirements; this implementation makes no residency guarantee.
