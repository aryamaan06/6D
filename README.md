# 6D Space

6D is a **space-sector-only** engineering assurance platform that connects design decisions to reproducible evidence across revisions. The current local backend reviews structured project requirements using bounded propulsion, static-beam, radiative and drag calculations, alongside a curated circular-orbit numerical verifier. It is pre-customer and does not establish commercial advantage or flight-tool validity.

The startup workspace was established October 10, 2026. The active product definition is [PROJECT_BRIEF.md](PROJECT_BRIEF.md), the full feature catalogue is [docs/PRODUCT_FEATURES.md](docs/PRODUCT_FEATURES.md), and [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) defines the active startup sequence with an October 21 working-capability checkpoint. [AGENTS.md](AGENTS.md) records working instructions. Arya continues implementation in the original **6D** chat. [Today's exact setup/review tasks](docs/TODAY_TASKS.md) and the [proposed screen specification](docs/SCREEN_SPEC.md) explain the next steps.

## Run the project foundation

```console
python run.py project-demo
```

This offline CLI demonstration writes three constructed project-review receipts under `artifacts/projects`: a baseline whose six declared requirements are met, a supplied revision with an unmet thermal limit, and that revision with an additional unsupported control requirement that leaves the review incomplete. It uses no inference or credentials. The revision comparison identifies affected evidence through explicit bindings; it does not infer physical coupling.

For a structured `sixd.project.v1` manifest and saved reviews:

```console
python run.py project-review PROJECT.json
python run.py project-review REVISED.json --compare-with artifacts/projects/OLDER.json
python run.py project-compare artifacts/projects/OLDER.json artifacts/projects/NEWER.json
python run.py project-verify artifacts/projects/REVIEW.json
```

The exported, explicitly constructed manifests in `examples/design-baseline.json`, `examples/design-revised.json` and `examples/design-missing_evidence.json` provide concrete accepted input examples. For instance: `python run.py project-review examples/design-baseline.json`.

[Foundation schema and boundaries](docs/FOUNDATION_BUILD.md) describe accepted inputs, exact units, source fingerprints and review states. Unknown models remain unresolved. These commands accept structured records, not executable uploads. Review records are internally checked and preserved through exclusive writes; their hashes are not authenticated signatures.

The project foundation is currently exposed through CLI. The existing browser below still presents the curated orbital workflow; the new product UI follows the screen review.

## Start the local interface

Requires Python 3.10 or newer. The app has **no third-party Python dependencies** and needs no API key, cloud account, paid inference or package download.

From this directory:

```console
python run.py serve
```

Open http://127.0.0.1:8766. Choose a curated example, review its contract, acknowledge the scope and run the checks. The screen displays measured evidence, the exclusions and the recorded versions. Download the JSON or inspect a previous snapshot. Stop the server with Ctrl+C.

After saving two audits, use **Compare saved audits** to inspect changed assumptions, source versions, verdicts and recorded measurements. Changing either selected snapshot clears the earlier comparison. Comparisons read saved evidence; they do not run inference or claim physical change-impact analysis.

On Arya's current Codex Windows host, the bundled Python can also be invoked in PowerShell:

```powershell
& 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' run.py serve
```

The server listens on loopback only and accepts registered curated selections. It is not a production host or an arbitrary-code sandbox.

## Reproducible demonstrations

```console
python run.py demo
```

This writes JSON and portable HTML evidence snapshots under `artifacts/`. Demonstration mode explicitly does not claim human sign-off. Expected *curated* outcomes:

| Example | Expected result |
| --- | --- |
| Correct velocity Verlet implementation | No defect found in supported checks |
| Seeded outward-force sign error | Defect likely |
| Correctly declared explicit Euler | Method limitation |
| Euler stepping under a second-order contract | Defect likely |
| Missing reference frame | Inconclusive; no numerical experiments |

These are constructed demonstrations, not a blinded benchmark or detection/false-accusation rates for customer code. They use exposed Python force and step functions, an analytic circular reference and time-step refinement.

To review an individual contract before an audit:

```console
python run.py contract --case verlet_correct
python run.py audit --case verlet_correct --accept-contract
```

Parameters remain adjustable rather than universal design targets. For example, `--radius 8000000` evaluates a different synthetic radius and creates a different contract hash:

```console
python run.py audit --case verlet_correct --radius 8000000 --accept-contract
```

To check or reproduce saved evidence, substitute an actual generated filename:

```console
python run.py verify artifacts/RECORD.json
python run.py reproduce artifacts/RECORD.json
python run.py compare artifacts/OLDER.json artifacts/NEWER.json
```

Reproduction checks source versions and compares the deterministic audit identity. Application writes are exclusive, preserving earlier snapshots. Digests are not authenticated signatures or tamper-proof storage.

## Verification

```console
python -m unittest discover -s tests -v
```

On October 14, all **197 tests passed**, including safe provider diagnostics, completion-budget/timeout regressions, bounded tool-protocol recovery and the private live-validation session. The earlier 115-test foundation also passed from a fresh Git checkout. The suite covers analytic/scaling references, invalid units/ranges, numerical precision, project requirements and revision dependencies, verification-source changes, quarter-orbit geometry, method reversibility, decoys, abstention, record integrity, safe inference errors, persistent spending limits, atomic rejected tool batches, exact finish evidence, correction exhaustion, profile request shapes, private-key cleanup, the two-case live acceptance gate and the local API. These are development checks, not independent user or benchmark results. On the Codex Windows sandbox, loopback API tests may need the app's reviewed permission to connect locally.

## What the increment contains

- Reviewed, versioned assumptions with units, reference frame and numerical method.
- Deterministic force/reference/refinement experiments and applicable Verlet reversibility checks in `src/sixd/kernel.py`.
- Four bounded deterministic engineering adapters and structured project/requirement review.
- Revision impact from explicit input/model/requirement/source dependencies, with immutable earlier snapshots.
- Evidence-linked findings, raw measurements, source fingerprints and mandatory exclusions.
- A local review interface and inspectable JSON/HTML records.
- Reproduction and contract/source comparison commands.
- [Verification scope](docs/VERIFICATION_SCOPE.md), [customer-discovery brief](docs/CUSTOMER_DISCOVERY.md) and [next development steps](docs/NEXT_STEPS.md).

**Live provider access is confirmed; a completed agent investigation is still pending.** Truncation recurred at the 8,192-token allowance after the tool-recovery fix. A new [private live-validation session](docs/LIVE_VALIDATION.md) tests three explicit Nano request profiles with one key entry and requires two complete investigations with independently verified evidence before saving a profile. The session ceiling is $0.10/15 reserved requests within the same $5 cumulative allowance. Thinking-control support is a hosted compatibility experiment, not an assumed property. Safe usage from rejected responses is now retained. Run `python run.py investigate --case euler_method_limit --provider fixture --accept-contract` for a visibly scripted offline demonstration, or use the local UI's fixture option. No fixture is presented as live Nemotron output. [Provider setup](docs/PROVIDER_SETUP.md) covers configuration and the persistent ledger; [live status](docs/LIVE_INTEGRATION_STATUS.md) records the actual receipts.

Customer code/solver integrations, perturbations and maneuver simulation, guarded patches, physical-test/telemetry integrations, authenticated team review and public deployment are not implemented. Passing these bounded requirements or numerical checks is not overall correctness, real-world model validation or certification.

No external outreach, code publication, commercial license, customer commitment or revenue is implied by this local build.
