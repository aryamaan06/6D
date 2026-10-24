# 6D

**Change a space-system design. See which engineering evidence needs rechecking.**

6D connects requirements, bounded calculations, saved revisions and supporting references. It identifies affected checks after a change, reuses eligible unchanged results, and keeps unmet criteria separate from missing evidence. NVIDIA Nemotron, running through Nebius Token Factory, investigates the recorded evidence and explains what to check next.

![6D showing calculated findings for a constructed engineering change](docs/images/6d-review.png)

*Actual application UI, calculated constructed reference: a changed heat input produces an unmet thermal criterion while unsupported control remains unassessed. This is not NASA/ISRO/SpaceX flight data. The screenshot was captured in an isolated reference workspace.*

## Try it

**Current delivery:** local desktop/browser application. A hosted judge URL is not available yet; protected judge access is tracked under Build F in the [submission checklist](docs/SUBMISSION_CHECKLIST.md). Opening localhost from another computer will not reach the developer's instance.

Python **3.10+** is required; the application runtime uses the standard library.

1. Clone this repository and enter its folder:
   ```console
   git clone https://github.com/aryamaan06/6D.git
   cd 6D
   ```
2. Prepare the local environment:
   ```console
   python tools/setup_local.py
   ```
3. Start the application, then open http://127.0.0.1:8768/:
   ```console
   python tools/open_preview.py
   ```

On Windows, `Setup-6D.cmd`, `Open-6D.cmd` and `Stop-6D.cmd` provide the same workflow; `py -3` may be used in place of `python`. On Linux/macOS, use `python3`. Windows has native launcher verification; the other platforms still need native qualification. [Setup, backup and recovery details](docs/RELEASE_HANDOVER.md).

A fresh checkout opens without saved private project data or provider credentials. Use **Import project** to choose a constructed reference, explicitly create it, and **Run checks**. **Guided review** follows a design change; **Powered flight** offers its existing vertical-ascent reference. Loading a page never silently calculates a new verdict. [Powered-flight walkthrough](docs/POWERED_FLIGHT.md).

## The engineering workflow

1. Supply project inputs, units, sources, model mappings and requirements using forms, CSV, values-only Excel or supported project JSON.
2. Calculate a saved baseline and inspect its findings, assumptions, numerical support and exclusions.
3. Edit a draft and preview the declared dependencies affected by a change.
4. Save the revision and explicitly rerun affected checks. Inspect calculation/reuse origins and compare retained runs.
5. Investigate a finding with Nemotron, review supporting references, track follow-up actions and export the evidence.

Working views include the system canvas/table/reader, review overview, change comparison, coverage, action queue, reports, orbital/vertical-flight playback, simulation-history imports and sampled operating-envelope studies. [Current capabilities and boundaries](docs/CONNECTED_REVIEW.md) · [Agreed A–F build scope](docs/HACKATHON_BUILD_SCOPE.md).

## How Nebius and Nemotron are used

The contextual Assistant calls **NVIDIA Nemotron through Nebius Token Factory** during actual investigations. It selects bounded evidence reads and supported reproducibility rechecks, then explains captured findings and missing evidence. The application owns numerical quantities, units, change directions and verdicts; model prose cannot replace them.

| Candidate | Recorded evidence | Current use |
| --- | --- | --- |
| Nano | Completed earlier case packs; rejected its first read action in the corrected October 20 three-case comparison, leaving two tasks untested. | Historical CLI configuration; not the selected browser Assistant. |
| Super | Selected from earlier reviewed comparison evidence. An October 20 explanation reversed a limit-change direction; a separate offline replay under the new guard rejects it. Four current constructed qualification cases completed after that correction. | Selected project Assistant. |
| Ultra | Completed all three October 20 corrected-contract cases; earlier failures and skipped cases remain recorded. It has not completed the current four-case pack. | Evaluated candidate; not enabled as an automatic deep mode. |

These observations concern particular protocols, cases and settings; they are not a universal model ranking. [Comparison results](docs/APPLICATION_ROLES_LIVE_RESULTS.md) · [Direction guard and replay](docs/CHANGE_DIRECTION_RESULTS.md) · [Latest live qualification](docs/AI_QUALIFICATION_RESULTS.md).

Connect a Nebius key privately through **Connect AI** after configuring an approved provider allowance. [Provider setup](docs/PROVIDER_SETUP.md). Local engineering calculations and saved evidence work without inference; new AI investigations require a usable Token Factory connection. No paid call occurs on startup or connection. The cumulative reservation ledger, per-job ceilings and no-retry policy remain enforced; reservations are not a provider invoice.

Tavily supplies explicit reference searches followed by human review/save/link steps. LangSmith receives only an explicitly approved, previewed metrics record. [Tavily live result](docs/TAVILY_LIVE_RESULTS.md) · [Connection and privacy details](docs/AI_QUALIFICATION.md). Each service has a separate private key form.

## Evidence, with scope attached

| Evidence | What it establishes |
| --- | --- |
| [1,000 generated edit cases, October 19](docs/RECALCULATION_VERIFICATION_RESULTS.md) | 742 valid edits matched full recalculation exactly; 258 invalid edits were consistently rejected. The same-calculator comparison checks reuse consistency, not independent physics correctness; this predates powered flight. |
| [30 published-reference/domain checks, October 19](docs/PUBLISHED_BENCHMARK_RESULTS.md) | Specified analytic, rounded and separate-tool checks across seven bounded models, with sources and tolerances. |
| [Current orbital reference comparisons](docs/NUMERICAL_ACCURACY_RESULTS.md) | Constructed cases compared with analytic/NASA CSPICE references after the RK4 improvement; numerical support remains separately gated. |
| [Powered-flight reference checks](docs/POWERED_FLIGHT_REFERENCE_RESULTS.json) | Recorded reference inputs, errors/tolerances and declared calculation scope. |
| [Current live Assistant qualification](docs/AI_QUALIFICATION_RESULTS.md) | Super completed four constructed evidence tasks with 16 accepted responses. Separate coding-agent AI review found no material error in those four explanations; independent human review remains pending. |

The October 24 full offline discovery executed 1,225 methods and exposed two test-fixture issues, including one cleanup error; both affected modules passed 11 tests after correction. The original full-run failure/skip record is retained; a clean full-suite rerun is not claimed. The skipped SciPy reference passed separately with its development dependencies.

[Validation index](docs/VALIDATION_INDEX.md) distinguishes historical full-suite counts, current targeted tests, browser assertions and reference checks. They are not additive. Full regression tests can be run with `python -m unittest discover -s tests`; they use synthetic provider transports, not paid inference.

## Submission-period development

The tracked repository begins on **October 14, 2026**. During October 14–24 the implementation added the engineering-evidence workspace, revision/reuse verification, authoring/intake, bounded orbital/flight calculations and accuracy gates, specialist history import, sampled studies, source/action/coverage workflows, and live Nemotron/Tavily/LangSmith integration. Dates and original outcomes remain in [historical development notes](docs/CHANGELOG.md).

The broader 6D concept predates some of this code. The repository history alone does not establish whether any earlier implementation existed before the submission period; the entrant must confirm that history in the submission. [Submission-period inventory](docs/SUBMISSION_PERIOD.md).

## Limits

The eight bounded models cover ideal propulsion, static beams, steady radiative equilibrium, single-condition drag, unforced two-body orbits, supplied power/energy budgets, single-axis spacecraft pointing and vertical ascent/coast. These are not complete engineering disciplines. Scalar links do not create simultaneous multiphysics coupling. Guided ascent, staging and project-wide AI investigations are planned in A–F, not delivered features.

There is no complete launch-to-orbit, reentry or landing simulator, hardware/flight qualification, customer validation or launch authorization. Current data/examples are constructed unless explicitly classified otherwise. Recorded playback is historical evidence, not a new live inference. The local loopback server must not simply be exposed publicly; Build F must provide appropriate access, isolation and spending controls.

## License and third-party notices

6D source is licensed under the [MIT License](LICENSE), approved by the project owner on October 24, 2026. Bundled third-party material retains its own notices; Lucide's license is preserved at [design/vendor/LUCIDE-LICENSE.txt](design/vendor/LUCIDE-LICENSE.txt). Referenced external tools/data are not relicensed by this repository.

Contributor instructions remain in [AGENTS.md](AGENTS.md); older planning records are archived under [docs/development](docs/development/README.md).
