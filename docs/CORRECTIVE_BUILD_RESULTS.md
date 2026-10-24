# Performance and correctness delivery

Delivered October 25, 2026 after the October 24 review. This corrects delivered functionality before E/F; it adds no engineering model, new feature letter or cloud deployment.

[Acceptance](CORRECTIVE_BUILD_ACCEPTANCE.md) · [Scoped verification record](validation/CORRECTIVE_BUILD_CHECKS.json) · [Paired performance measurements](HISTORY_PERFORMANCE_RESULTS.json).

## Measured history performance

An isolated snapshot of commit `c76d0b6` and the candidate used identical constructed orbital histories with 2, 7 and 13 revisions, a fixed 512-step retained grid, two warm reads and two new-store reads at each checkpoint. Fixed time/UUID generation allowed comparison of complete returned views, including evidence digests and execution origins. All views and verifier source hashes matched exactly.

| At thirteen revisions | Previous median | Updated median |
| --- | ---: | ---: |
| Warm read | 1.074 s | 0.056 s |
| New-store read | 0.947 s | 0.280 s |
| Save, cumulative per-revision sample median | 0.486 s | 0.039 s |
| Run, cumulative per-revision sample median | 1.093 s | 0.265 s |

Warm reads made zero full-review verification calls instead of fifteen per read; new-store reads made four instead of fifteen. The returned payload remained 658,096 bytes. New-store means a new application object cache, not a flushed OS/disk cache. Measurements came from shared development hardware and do not guarantee these times for other resolutions, histories, machines or deployments. This does not reproduce Claude's unknown workload exactly.

The first benchmark harness attempt lost its report during Windows cleanup because its read connection was not closed. That harness issue was fixed; preliminary 2048-step attempts were excluded. The final paired 512-step result preserves each checkpoint and its baseline before comparison. A preliminary recalculation run was stopped after a source changed; only the final source-stable 1,000-case run is counted.

## Storage behavior and integrity

The workspace selects and fully verifies the current/prior/displayed or reuse-consumed receipts. Bounded immutable-string caches are keyed by actual stored payload bytes, row identity and current verifier context. Fresh JSON objects protect the cache from caller mutation. Payload budgets are 16 MiB for verified receipts, 2 MiB for summaries and 1 MiB for comparisons, excluding Python overhead and returned objects.

Every ordinary history read still hashes retained receipt bytes and checks compact metadata, review checksums, identities, source/version metadata, origins and revision snapshots. Historical trajectory numerical consistency is now lazy: it is checked when that receipt is displayed or used, rather than certifying every unselected historical trajectory on every page load. This change is explicit. A read transaction pins metadata/refetch to one database snapshot; a WAL concurrency regression checks that a concurrent edit is seen coherently and then rejected on the next read when corrupt.

SQLite builds without JSON projection retain the slower full-verification fallback. Large payload serialization and history-byte scans can still grow; this is not a production-scale database redesign. Digests remain unsigned consistency checks, not tamper-proof authentication.

## Explanation corrections

The raw legacy/minimal quality path treated the word met inside not met as a positive signal. The active numerical-role policy already rejected that plain contradiction through a separate check. Status polarity is now centralized, covering explicit positive/negative/unassessed claims, passive forms, bounded negation, questions and conditional review language while preserving the distinct truth of captured observations and attributed source quotes.

Direction coverage includes additional up/down synonyms and rejects unsupported criterion-relaxation claims without guessing the effect of an unknown operator. Legacy quantity inspection recognizes common prefixes such as km, kN and MPa literally, without converting/adopting prose as evidence. Current commentary continues to forbid numerical literals and keeps exact statuses, changes and quantities application-owned. Whole-project status claims bind named requirements rather than comparing every sentence against every mixed finding.

These are incomplete English heuristics. Duplicate/overlapping titles can remain ambiguous; unitless/word quantities and arbitrary paraphrases are not universally understood. No clean phrase check proves semantic accuracy. Existing saved live receipts were not rewritten, and no paid requalification was run after these source changes.

## Canonical source bytes and numerical evidence

Six runtime files were aligned from CRLF to LF. Their Python ASTs were unchanged, and their resulting bytes matched the LF files already published in Git. Raw-byte fingerprints remain honest: original receipts keep their original hashes and may be historical against the current checkout. No old hash was silently relabelled and no historical calculation was automatically rerun.

`python tools/check_source_consistency.py` verifies the LF policy and 58 runtime Python files; optional `--git-ref HEAD` compares exact committed bytes after publication. Rerun the selected project's checks explicitly to create current evidence. A fresh Linux/container deployment should seed and calculate inside its canonical checkout; native Linux hosting qualification remains part of F.

Twenty existing separate-reference cases passed under the canonical sources: eight analytic/NASA CSPICE orbital comparisons and four each for vertical, prescribed planar and staged ascent against separate SciPy equations. [New source-bound report](validation/CANONICAL_SOURCE_REFERENCE_RESULTS.json). Numerical equations were not changed; these constructed comparisons do not validate a real vehicle.

## Regression outcomes

- Source-stable1,000-case recalculation rerun: 742 valid edits exactly equivalent to full calculation and 258 invalid edits consistently rejected; zero discrepancies. An independent dependency-closure audit checked 1,925 reused model results and passed. The existing eight-family edit distribution is finite and predates some later flight adapters; separate references/tests cover those adapters.
- Full offline discovery: 1,338 methods, three outdated model-count/source-list assertion failures, zero errors and three development-only SciPy skips. The expectations were updated for the already-existing ten models/guided/staged verifier files; the three affected modules then passed 37 methods. A clean subsequent full-suite run is not claimed. The three skipped numerical reference tasks were exercised separately in the 20-case development run.
- Twelve storage/performance/tamper regressions and 131 overlapping targeted guard-related methods passed. These counts overlap full discovery and are not additive.
- Six actual synthetic-provider browser groups passed for project entry/no inference, explicit completion and metrics, captured citations, separate requirement scope/history, saved receipt reload and fresh narrow-screen access. The real app delivery check showed the retained live receipt with no page errors and no POST requests.

All 21 checked private storage tables retained exactly their rows/counts. Provider configuration/encrypted credential file hashes and the spending ledger were unchanged. No paid model calls, Tavily searches, LangSmith uploads, stronger-model activation or user-data migration occurred.

## Open and remaining work

Open **http://127.0.0.1:8768/** and refresh; verified build **4050616b75d1**. Earlier reviews whose raw source fingerprints differ remain preserved as historical. Choose **Run checks again** for a selected saved project when current evidence is needed; the build does not silently create fresh verdicts for user projects. The existing remembered Nebius connection restores privately.

E remembered Tavily/LangSmith connections and F protected hosted access remain pending, followed by the separately acknowledged interface refinement, founder walkthrough, outside-user evidence and submission materials. Earlier live AI qualification is historical after these guard/source changes; final current-build live checks remain necessary before claiming current live behavior in the submission.
