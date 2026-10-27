# Current application state

Status date: **October 27, 2026**. This page distinguishes implemented capabilities from recorded validation and remaining work. It supersedes dated build descriptions as the entry point to the project; historical outcomes remain unchanged.

## Product and delivery

6D is a local engineering-evidence workspace for proposed space systems. Its central workflow is **design → calculate → change → recalculate → compare → investigate → report**. The application preserves the difference between a calculated unmet criterion and a requirement that has not been assessed.

- **Local application:** implemented at http://127.0.0.1: 8768/ on the machine running it.
- **Protected hosting package:** implemented with invitation access, isolated visitor state and recorded Linux/container checks.
- **Public hosted demo:** not deployed. No public URL, production uptime or cloud operational qualification is claimed.
- **Customer or flight qualification:** not established. Current example projects are constructed unless labelled otherwise.

[Local opening/update instructions](OPEN_6D.md) · [Hosting evidence and outstanding deployment work](BUILD_F_RESULTS.md).

## Engineering coverage

The maintained adapters expose these **ten bounded models**:

| Model | Scope |
| --- | --- |
| Ideal propulsion | Ideal rocket-equation budgets under declared burn assumptions |
| Static cantilever | Supplied beam geometry and static tip loading |
| Radiative equilibrium | Declared steady grey-surface radiation balance |
| Drag load | Supplied single-condition density, speed, coefficient and area |
| Orbital trajectory | Unforced point-mass two-body propagation |
| Power/energy budget | Supplied loads, generation and usable energy accounting |
| Attitude control | Bounded single-axis spacecraft pointing model |
| Powered vertical flight | Vertical ascent/coast with declared thrust, atmosphere and gravity assumptions |
| Prescribed planar ascent | Planar motion with a supplied steering programme |
| Variable-thrust serial staging | Bounded stage profiles, fuel events, separation and ignition delays |

Model completion does not establish suitability for an arbitrary vehicle. Scalar links propagate declared quantities; they do not create simultaneous multiphysics coupling. Prescribed ascent steering is not closed-loop launch GNC. A model's applicable inputs, numerical support, assumptions and exclusions remain part of the finding.

## Connected workflow

Implemented views include project intake, shared draft authoring, system canvas/table/reader, requirements, coverage declarations, dependency tracing, change comparison, targeted recalculation, saved simulation playback, simulation-history imports, sampled studies, scalar test comparisons, sources, follow-up actions and review reports.

Inputs use explicit units and source statements. Historical revisions remain read-only. A new draft, saved revision and explicit calculation are distinct actions. Display rounding and SI superscripts do not modify exact stored values or exported evidence.

### Current interface correction

The conversation has a larger reading area and an **Expand / Restore size** control. New conversations start at **Choose a model**; the user explicitly selects Nano for quick explanations, Super for everyday review or Ultra for deeper reasoning. These are suggested roles, not accuracy guarantees. Model choice is retained within a conversation rather than silently choosing a server default for a new one.

Progressive disclosures preserve the opened section's beginning so the reader can proceed downward. Numerical evidence, activity and technical settings remain available behind details. These UI changes have offline verification; they do not establish live answer quality. [Correction results](CHAT_READABILITY_RESULTS.md).

## AI and external services

| Service | Implemented role | Validation boundary |
| --- | --- | --- |
| Nebius Token Factory / NVIDIA Nemotron | Requirement and whole-project investigations; explicit Nano/Super/Ultra selection; bounded evidence reads and supported rechecks; retained questions, outcomes and source identities | Current-source success must be established by a completed live record. Older successes do not automatically qualify newer prompts or conversation handling. |
| Tavily | Explicit search, result preview and manual source save/link | Retrieved text remains supplemental and unverified; it cannot change a numerical finding. |
| LangSmith | Previewed, explicitly approved metrics export | Historical upload evidence is not continuous telemetry or a new evaluation result. |

Per-job and shared cumulative reservations persist; failed requests retain their reservations. Model selection itself sends no request. No automatic model escalation or transport retry is enabled. Credentials use separate forms; optional Windows-encrypted remembering restores connections without contacting providers.

Images selected in the assistant are **local previews**. Only the user's written notes are submitted to the three integrated text models. No image interpretation or OCR capability is claimed.

### Latest completed live observation

Build **cbd5b64fe0be** completed **six of six** live jobs: one first answer and one model-local follow-up for each of Nano, Super and Ultra on the same constructed R3 burnout-altitude evidence. The phase used30 requests and **USD 0.56654448 reserved**. Each supplied a useful definition and relevant next check in development review. Nano is repetitive and loosely links criterion satisfaction with internal consistency; Super's design wording needs its declared-criterion scope; Ultra is verbose with an imperfect analogy. This is not independent human review or comprehensive semantic qualification.

[Latest sanitized phase](validation/CHAT_READABILITY_LIVE_BATCH4.json) · [complete correction/results](CHAT_READABILITY_RESULTS.md). Across four separately approved phases, 20 jobs/100 requests reserved **USD 1.81489076**, not confirmed billed cost. Original failures are unchanged. A prior completed Super answer overclaimed space entry/obstacle clearance; the new guard rejects that assurance offline, while preserving the original receipt. The current phase did not repeat it. No automatic retries, image transfers, Tavily searches or LangSmith uploads occurred.

Historical [initial failures](validation/CHAT_READABILITY_LIVE_BATCH1.json), [second phase](validation/CHAT_READABILITY_LIVE_BATCH2.json), [third-phase quality findings](validation/CHAT_READABILITY_LIVE_BATCH3.json), the [earlier output-limit receipt](validation/FOCUS_BUILD3_LIVE_CHECK.json) and older model qualifications retain their original source/settings limits. No Lightning migration, project deletion or public deployment is included.

## Reading the evidence

Start at the [validation index](VALIDATION_INDEX.md). It links numerical references, targeted/full recomputation checks, browser behavior, retained live outcomes and their limitations. A historical full-suite caveat must not be overwritten by a later smaller passing run, and counts from overlapping runs must not be added together.

The October 19 generated-edit study checked software reuse consistency against full recomputation by the same calculators. Published analytic/external-tool references provide different evidence. Neither replaces independent human assessment of a real design's model applicability.

## Remaining release gaps

- Broader question sets, outside-user answer review and remaining wording/readability limitations; the six-turn constructed conversation path has passed its scoped check.
- Founder walkthrough and any further observed interface defects.
- Public hosting, access/TLS/persistence/spending verification and final submission materials.
- Outside-user sessions and independent engineering review.

No whole-vehicle readiness, complete rocket physics, authenticated engineering approval, production security or mission-success guarantee is claimed.

[Repository guide](REPOSITORY_GUIDE.md) · [Complete chronology](PROJECT_RECORD.md) · [Submission checklist](SUBMISSION_CHECKLIST.md).
