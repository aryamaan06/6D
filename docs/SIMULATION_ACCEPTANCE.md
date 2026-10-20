# 6D — 3D orbital simulation acceptance

Date: October 17, 2026, Asia/Calcutta. Delivery build: `e933bbe19653` at http://127.0.0.1:8768/ . This records the bounded orbital milestone, not full-product completion or flight validation.

## Delivered behavior

The connected workspace now accepts explicit 3D position and velocity, gravity, an exclusion radius, duration and fixed step count. Local velocity-Verlet integration produces saved SI state histories. The Simulation view offers camera rotation/zoom, 3D/XY/XZ/YZ projections, play/pause/rate/scrub controls, synchronized history graphs, exact sample values, compatible stored-run comparison, source disclosures and JSON export.

Every receipt stores its explicit scenario and exact immutable project revision. Scenario inputs remain separate from the project's static component inputs. No requirement verdict, AI investigation, provider selection or spending allowance is changed by a simulation.

## Automated verification

- The full repository suite passed: **441 tests**, `python -m unittest discover -s tests`, with isolated databases and loopback test servers. It completed in 54.088 seconds in this environment.
- Numerical references cover inclined circular motion, eccentric Kepler motion, arbitrary three-axis rotation, second-order refinement, time reversibility and dimensional similarity. Domain tests reject unsupported frames/fields, invalid or nonfinite inputs, contact/radial/escape cases, poorly resolved steps and unbounded work.
- Storage/API tests cover exact revision/snapshot binding, immutable reopen, no recomputation on reads, stale-source detection, source edits during execution, digest/binding corruption, compatibility, concurrent-run refusal, bounded requests and local Host/Origin/runtime safeguards.
- Both JavaScript files passed Node syntax checks.

## Actual browser workflow

`work/simulation-browser-acceptance.json` records **11 passing browser check groups** using actual local calculations in a fresh temporary database on port 8773. No founder database, paid provider or live credentials were used for these mutations.

The checks exercised default and custom arbitrary-plane circular scenarios, exact receipt/UI values at multiple samples, genuine positive/negative Z histories, camera/projection changes without evidence changes, keyboard rotation, zoom, play/pause, rates, scrub, end/restart behavior and JSON export. Comparing different grids retains each nearest sample's exact time; a shorter history has no invented sample beyond its end. Chart selection follows the displayed shared time axis.

Reload preserved records without a new run. Coarse-step and empty-field rejection created no completed receipt. Drafts blocked new calculation; saving a new project revision did not fabricate an orbit for it. Explicitly reopened older runs retained their historical label and original samples. The existing thermal-change/save/rerun/report/Inspector journey still calculated its unmet threshold. Browser JavaScript errors, external network requests and AI/investigation POSTs were absent.

The two constructed circular cases were also compared with independently calculated analytic circular positions in browser QA:

| Case | Maximum position error divided by declared orbital radius |
| --- | --- |
| Inclined default, 1024 steps | 0.00008239022857281046 |
| Arbitrary-plane custom, 512 steps | 0.00023363467679998553 |

These are finite-step errors for these specific synthetic cases. They are not general accuracy bounds, physical-validation evidence or mission-success estimates. Energy conservation alone does not bound trajectory error.

Desktop comparison and 390-pixel mobile screenshots were visually inspected. The narrow view has no document overflow with setup, sample values and provenance open. Exact tables retain local horizontal scrolling where necessary.

## Failure and delayed-response checks

`work/simulation-browser-guards.json` records a separate passing check with actual saved scenarios using different gravity values: the overlay was rejected and the selected original sample stayed exact. It also records five deliberately injected transport/presentation cases, kept separate from actual numerical evidence:

1. A history-list GET returned 503 after a successful calculation/save POST. The new receipt ID, picker, exact initial sample and saved status stayed consistent; a secondary-history warning appeared.
2. A stale-source flag showed the saved run as historical while preserving its samples.
3. A restart-required status disabled new calculation and retained saved playback.
4. An export response was delayed while another run was selected. The downloaded receipt and filename retained the original requested identity.
5. An old-project detail response was delayed across a project switch. It could not populate the new project's viewer or sample table.

These checks found no JavaScript errors, external requests or AI calls. A review-discovered mixed-receipt failure path was corrected before these checks: saved result data and displayed identity are now committed together even when the secondary history refresh fails.

## Update and founder-data preservation

Before restart, the existing workspace SQLite database was backed up under ignored `.local/backups/`. After loading the new backend, all preexisting rows matched that backup exactly: one project, one revision, six static runs, two project investigations and two model comparisons. SQLite integrity check returned `ok`. The founder database contains no test simulation receipts; the first scenario is calculated only when the user chooses **Calculate & save run**.

`work/live-simulation-smoke.json` confirms the production local address serves build `e933bbe19653`, reports no restart required, opens the simulation form and returns to the existing Reader. The read-only smoke generated no POSTs or JavaScript errors. No paid model call was made in this milestone. Existing provider configuration and the cumulative allowance were preserved; a server restart clears the private in-memory key as usual.

## Scope and limits

This is an unpowered elliptic two-body point-mass model. It does not simulate engines, atmosphere, attitude, launch/landing, heating, structural response, perturbations, uncertainty or complete vehicle behavior. Inputs have explicit sources but their applicability to a real system is not independently established. The scene shows a declared exclusion sphere and an enlarged point marker; it does not infer CAD or terrain.

Project requirement mappings for dynamic histories, automatic scenario coupling to static input edits, external solver import and physical-test comparisons remain future work. The full feature catalogue remains the product direction.

See [SIMULATION_PLAYBACK.md](SIMULATION_PLAYBACK.md) for the contract and [TODAY_TASKS.md](TODAY_TASKS.md) for the founder walkthrough.
