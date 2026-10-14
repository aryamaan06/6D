# First working increment

Completed October 10, 2026, Asia/Calcutta.

## Delivered

Local numerical verifier and review interface for synthetic circular-orbit examples; explicit reviewed contracts; independently computed force/reference/refinement checks; repeated initial-phase checks; evidence-linked findings; versioned JSON/HTML snapshots; mandatory not-tested lists; reproduction and comparison commands. The source, setup and coverage are documented in README.md and VERIFICATION_SCOPE.md.

## Measured development results

- Twenty backend tests passed, including independent quarter-orbit geometry, time reversal, two seeded defect cases, an Euler method-limitation decoy, abstention, reproduction, report consistency and API review checks.
- The headless browser workflow passed for all five curated examples, including evidence download, inspection of an existing record and outer-page layout at desktop and mobile widths. Source, measurements and exclusions are visible in the reading interface.
- A selected-contract change clears the displayed result so previous evidence is not silently reused for the next selection.
- Saved evidence records were read back and their internal digests checked. Every generated record includes exclusions and records zero model calls.

These are constructed development demonstrations and tests. They are not a blinded general benchmark, validation of customer workflows, a false-accusation rate, real-world model validation or commercial traction.

## Runtime

Python 3.12.14 from the Codex bundled runtime; no third-party Python dependencies used. Loopback-only review URL: http://127.0.0.1:8766. The server is running for the current local session; restart with python run.py serve if it stops. Windows sandbox loopback restrictions required reviewed tool execution for local API/browser checks; no external requests or paid inference were performed by the app.

## Next milestone

One reviewed external mission-analysis model/workflow and an applicable independent reference. First confirm the task, operating conditions, data ownership and setup burden. A customer adapter and replaceable model-reasoning layer are future work, subject to exact API/license verification and a spend cap before live calls. Customer discovery is prepared but no messages were sent.
