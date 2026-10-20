# 6D visual evidence delivery

October 16, 2026, Asia/Calcutta. This increment advances the existing visual-evidence milestone without new engineering adapters, provider changes or paid calls.

## Implemented

- Reader plots the selected system's saved numerical requirement findings. Report plots the whole project; the requirement Inspector uses the same rendering.
- Each current or compatible historical row carries its own result, limit, comparison operator and canonical status. Changing a limit does not retroactively alter the earlier finding.
- Each requirement has a separate scale and explicit unit. Negative, zero and extreme finite values are normalized safely for display. Missing or incompatible numeric evidence is not plotted.
- Normal display numbers are rounded for readability; exact equality or values that would otherwise display identically retain sufficient saved precision. Source disclosures retain full saved values, run IDs and review digests.
- Historical rows require matching model ID, metric and unit. Changed source/adapter provenance is labelled, including earlier runs of the same revision. Drafts and revisions without current evidence show an instruction to save/run rather than a predicted result.
- Unsupported requirements remain separately visible, with canonical status and reason. Failure wording is criterion-neutral: Not met, including minimum and equality requirements.
- Inspect evidence keeps the selected requirement in context. Existing tables, model assumptions, exclusions and evidence JSON remain available.
- Print report / Save PDF uses the browser's native print dialog. It prints the complete saved report, including source disclosures, and restores the user's on-screen disclosure state. No project record or model call is created by printing.

These are saved scalar comparisons, not trajectories, time histories, sensitivity sweeps, coupled vehicle simulation, independent physical validation or launch authorization.

## Verification

JavaScript syntax check passed. All 13 focused workspace API regressions passed against a temporary database. A read-only headless Chrome smoke check of the delivered address passed: six numeric plots, unsupported control without a fabricated plot, print action/disclosure restoration, print layout, 390px plot layout with zero overflow, no JavaScript errors and no POST requests.

Final isolated Chrome acceptance passed on build 5022d4c287d9: 11 core checks plus five separately labelled synthetic presentation checks. Actual local API calculations verified baseline, a 700 W revision, a limit-only revision with unchanged metric/zero newly executed adapters, minimum/equality criteria, Reader scope, contextual inspection, source IDs, draft/unreviewed suppression, printing and narrow layouts. Equality precision is consistent in plots, requirement tables and Inspector.

Separate synthetic presentation fixtures verified exclusion of prior metric/unit mismatches, changed source/adapter warnings for earlier runs of the same revision, finite bounded SVG coordinates at +/-1e308 and stale-result suppression. They test rendering guards, not physical model validity.

Native Chrome A4 printing produced an eight-page QA report. All pages were rendered through Poppler and visually inspected for clipping/overlap; final rendered pages were byte-identical to the inspected layout. PDF text checks confirmed required report content and absence of the key-connection dialog. Native beforeprint/afterprint restored the earlier disclosure state. The QA PDF was an intermediate artifact, not a delivered mission report.

Final opening: http://127.0.0.1:8768/, footer Build 5022d4c287d9. No backend restart was required by these frontend changes; the previously stopped application was started and verified. The isolated QA server was stopped afterward. No provider setting, spending cap, ledger reservation or saved founder revision was changed by this milestone. No paid model call ran.

Local QA artifacts are under ignored work/: live-plots-smoke.mjs, live-plots-smoke.json, live-result-plots.png, live-result-mobile.png and live-result-print-layout.png, plots-browser-acceptance.json, plots-pdf-acceptance.json and retained plots-page-*.png renders. They are development artifacts, not customer or flight evidence.

## Open

Open http://127.0.0.1:8768/ and refresh. Choose a saved reviewed revision, then Reader or Report. If the server is stopped, use Open-6D.cmd; see OPEN_6D.md.
